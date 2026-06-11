import math
import os
import torch
import torch.nn as nn
import torchvision.models as models
from sympy.codegen import Print
from lib.pvt import pvt_v2_b2
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter
from torchvision.ops import DeformConv2d
import torchvision.ops
from pathlib import Path


def _load_torch_checkpoint(file_path, map_location="cpu"):
    try:
        return torch.load(file_path, map_location=map_location, weights_only=True)
    except TypeError:
        return torch.load(file_path, map_location=map_location)


def _resolve_pvt_weight_path():
    env_path = os.getenv("BFNET_PVT_PATH", "").strip()
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    bfnet_root = Path(__file__).resolve().parents[1]
    candidates.extend(
        [
            bfnet_root / "pvt_v2_b2.pth",
            bfnet_root / "model" / "pvt_v2_b2.pth",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("pvt_v2_b2.pth not found")


class BasicConv2d(nn.Module):
    def __init__(self, in_planes, out_planes, kernel_size, stride=1, padding=0, dilation=1, relu=False):
        super(BasicConv2d, self).__init__()

        self.conv = nn.Conv2d(in_planes, out_planes,
                              kernel_size=kernel_size, stride=stride,
                              padding=padding, dilation=dilation, bias=False)
        self.bn = nn.BatchNorm2d(out_planes)
        self.relu = nn.ReLU(inplace=True) if relu else None

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        if self.relu is not None:
            x = self.relu(x)
        return x


def conv(in_channels, out_channels, kernel_size, bias=False, stride=1):
    return nn.Conv2d(
        in_channels, out_channels, kernel_size,
        padding=(kernel_size // 2), bias=bias, stride=stride)


class ASPPConv(nn.Sequential):
    def __init__(self, in_channels, out_channels, dilation):
        modules = [
            nn.Conv2d(in_channels, out_channels, 3, padding=dilation, dilation=dilation, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU()
        ]
        super(ASPPConv, self).__init__(*modules)


class ASPPPooling(nn.Sequential):
    def __init__(self, in_channels, out_channels):
        super(ASPPPooling, self).__init__(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(in_channels, out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU())

    def forward(self, x):
        size = x.shape[-2:]
        for mod in self:
            x = mod(x)

        return F.interpolate(x, size=size, mode='bilinear', align_corners=False)


class ASPP(nn.Module):
    def __init__(self, in_channels, atrous_rates=[6, 12, 18], out_channels=32):
        super(ASPP, self).__init__()
        modules = []

        modules.append(nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU()))

        rates = tuple(atrous_rates)
        for rate in rates:
            modules.append(ASPPConv(in_channels, out_channels, rate))

        modules.append(ASPPPooling(in_channels, out_channels))

        self.convs = nn.ModuleList(modules)

        self.project = nn.Sequential(
            nn.Conv2d(len(self.convs) * out_channels, out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(),
            nn.Dropout(0.5))

    def forward(self, x):
        res = []
        for conv in self.convs:
            res.append(conv(x))
        res = torch.cat(res, dim=1)
        return self.project(res)


class LFG(nn.Module):
    """优化版轻量级频域引导器 - 修复维度问题"""

    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.patch_size = 8
        self.dct_size = self.patch_size * self.patch_size

        # 注册DCT基础权重
        self.register_buffer('dct_weights', self.init_dct_weights())

        # 引导网络
        self.guide_conv = nn.Sequential(
            nn.Conv2d(channel, max(4, channel // 8), 1),
            nn.GELU(),
            nn.Conv2d(max(4, channel // 8), channel, 1),
            nn.Sigmoid()
        )

        # 通道适配器
        self.adapter = nn.Conv2d(channel, channel, 1)

        # 分组归一化
        self.gn = nn.GroupNorm(min(8, channel), channel)

    def init_dct_weights(self):
        """初始化DCT权重 - 修复通道维度问题"""
        size = self.patch_size
        n = size * size
        weight = torch.zeros(n, n)

        for i in range(size):
            for j in range(size):
                basis = torch.zeros(size, size)
                for k in range(size):
                    for l in range(size):
                        basis[k, l] = math.cos(math.pi * (k + 0.5) * i / size) * \
                                      math.cos(math.pi * (l + 0.5) * j / size)
                weight[i * size + j, :] = basis.flatten()

        # 扩展为多通道版本 (C, n, n)
        return weight.unsqueeze(0).repeat(self.channel, 1, 1)

    def forward(self, x):
        B, C, H, W = x.shape
        patch_size = self.patch_size

        # 确保尺寸是patch_size的倍数
        pad_h = (patch_size - H % patch_size) % patch_size
        pad_w = (patch_size - W % patch_size) % patch_size
        x_padded = F.pad(x, (0, pad_w, 0, pad_h))
        H_pad, W_pad = H + pad_h, W + pad_w

        # 计算块数量
        num_patches_h = H_pad // patch_size
        num_patches_w = W_pad // patch_size
        num_patches = num_patches_h * num_patches_w

        # 分块处理 - 使用分组视图代替unfold
        x_blocks = x_padded.view(B, C, num_patches_h, patch_size, num_patches_w, patch_size)
        x_blocks = x_blocks.permute(0, 1, 2, 4, 3, 5).contiguous()
        x_blocks = x_blocks.view(B, C, num_patches, patch_size * patch_size)

        # 应用DCT变换 - 修复维度问题
        dct_blocks = torch.matmul(x_blocks, self.dct_weights.transpose(1, 2))

        # 重组特征图
        dct_blocks = dct_blocks.view(B, C, num_patches_h, num_patches_w, patch_size, patch_size)
        dct_blocks = dct_blocks.permute(0, 1, 2, 4, 3, 5).contiguous()
        dct_feat = dct_blocks.view(B, C, H_pad, W_pad)

        # 裁剪回原始尺寸
        dct_feat = dct_feat[:, :, :H, :W]

        # 频域特征适配
        adapted = self.adapter(dct_feat)
        adapted = self.gn(adapted)

        # 生成空间引导
        spatial_guide = self.guide_conv(adapted)

        return x * spatial_guide


class FSRCB(nn.Module):
    """优化版频谱-空间残差块"""

    def __init__(self, channel, kernel_size=3, reduction=4, bias=False, act=nn.ReLU(), n_resblocks=2):
        super().__init__()
        self.freq_att = LFG(channel)

        # 空间注意力
        self.sk_conv = nn.Sequential(
            nn.Conv2d(channel, max(4, channel // 8), 1),
            nn.ReLU(),
            nn.Conv2d(max(4, channel // 8), channel, 1),
            nn.Softmax(dim=1)
        )

        # 残差块
        self.resblocks = nn.Sequential(
            *[RCAB(channel, kernel_size, reduction, bias, act)
              for _ in range(n_resblocks)]
        )

        # 动态融合权重
        self.alpha = nn.Parameter(torch.tensor(0.5))

        # 通道重校准
        self.channel_att = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channel, max(4, channel // reduction), 1),
            nn.ReLU(),
            nn.Conv2d(max(4, channel // reduction), channel, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        # 频域增强
        freq_feat = self.freq_att(x)

        # 空间注意力
        sk_weight = self.sk_conv(x)
        spatial_feat = x * sk_weight

        # 动态融合
        fused = self.alpha * freq_feat + (1 - self.alpha) * spatial_feat

        # 通道重校准
        channel_att = self.channel_att(fused)
        calibrated = fused * channel_att

        # 残差连接
        return self.resblocks(calibrated) + x


class RCAB(nn.Module):
    """残差通道注意力块 - 兼容修复"""

    def __init__(self, n_feat, kernel_size, reduction, bias, act):
        super().__init__()
        modules_body = [
            conv(n_feat, n_feat, kernel_size, bias=bias),
            act,
            conv(n_feat, n_feat, kernel_size, bias=bias)
        ]
        self.body = nn.Sequential(*modules_body)
        self.CA = CALayer(n_feat, reduction, bias=bias)

    def forward(self, x):
        res = self.body(x)
        res = self.CA(res)
        return res + x


def conv(in_channels, out_channels, kernel_size, bias=False, stride=1):
    """标准卷积层"""
    return nn.Conv2d(
        in_channels, out_channels, kernel_size,
        padding=(kernel_size // 2), bias=bias, stride=stride)


class CALayer(nn.Module):
    """通道注意力层"""

    def __init__(self, channel, reduction=16, bias=False):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.conv_du = nn.Sequential(
            nn.Conv2d(channel, max(4, channel // reduction), 1, padding=0, bias=bias),
            nn.ReLU(inplace=True),
            nn.Conv2d(max(4, channel // reduction), channel, 1, padding=0, bias=bias),
            nn.Sigmoid()
        )

    def forward(self, x):
        y = self.avg_pool(x)
        y = self.conv_du(y)
        return x * y


class DeformableConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, padding=1):
        super().__init__()
        self.offset_conv = nn.Conv2d(in_channels, 2 * kernel_size * kernel_size, kernel_size, padding=padding)
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, padding=padding)

    def forward(self, x):
        offset = self.offset_conv(x)
        x = torchvision.ops.deform_conv2d(x, offset, self.conv.weight, self.conv.bias, padding=1)
        return x

class DynamicInteractionUnit(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channels, channels // reduction, 1),
            nn.ReLU(),
            nn.Conv2d(channels // reduction, channels, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return x * self.mlp(x)

class UnifiedCollaborativePyramid(nn.Module):
    def __init__(self, in_channels, out_channels, num_levels=4):
        super().__init__()
        self.num_levels = num_levels
        self.level_convs = nn.ModuleList()
        current_channels = in_channels

        for _ in range(num_levels):
            self.level_convs.append(
                nn.Sequential(
                    DeformableConv2d(current_channels, out_channels),
                    DynamicInteractionUnit(out_channels)
                )
            )
            current_channels = out_channels

        self.fuse_conv = nn.Conv2d(num_levels * out_channels, out_channels, 1)

    def forward(self, x):
        features = []
        current_x = x
        original_size = x.shape[2:]  # 记录初始尺寸 [H, W]

        for i, conv in enumerate(self.level_convs):
            if i > 0:
                current_x = F.interpolate(current_x, scale_factor=0.5, mode='bilinear', align_corners=False)
            current_x = conv(current_x)
            # 将当前层输出插值回初始尺寸
            resized_x = F.interpolate(current_x, size=original_size, mode='bilinear', align_corners=False)
            features.append(resized_x)

        # 自底向上融合（此时所有特征图尺寸一致）
        for i in range(self.num_levels - 2, -1, -1):
            features[i] = features[i] + features[i + 1]

        fused = torch.cat(features, dim=1)
        return self.fuse_conv(fused)


class GGA(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=1, bias=False):
        super(GGA, self).__init__()
        self.gate_conv = nn.Sequential(
            nn.BatchNorm2d(in_channels+1),
            nn.Conv2d(in_channels+1, in_channels+1, 1),
            nn.ReLU(),
            nn.Conv2d(in_channels+1,  1, 1),
            nn.BatchNorm2d(1),
            nn.Sigmoid()
        )
        self.out_cov = nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, bias=bias)

    def forward(self, in_feat, gate_feat):
        attention_map = self.gate_conv(torch.cat([in_feat, gate_feat], dim=1))
        in_feat = (in_feat * (attention_map + 1))
        out_feat = self.out_cov(in_feat)
        return out_feat

# class StdPool(nn.Module):
#     def forward(self, x):
#         b, c = x.shape[:2]
#         std = x.view(b, c, -1).std(dim=2, keepdim=False)
#         return std.view(b, c, 1, 1)


class StdPool(nn.Module):
    """标准差池化（保持空间维度）"""

    def forward(self, x):
        """
        输入形状: [B, C, H, W]
        输出形状: [B, 1, H, W]
        """
        b, c, h, w = x.size()
        # 计算每个通道的标准差
        std = x.view(b, c, -1).std(dim=2, keepdim=True)  # [B, C, 1]
        std = std.view(b, c, 1, 1)  # [B, C, 1, 1]
        # 扩展为与输入相同的空间维度
        std_expanded = std.expand(-1, -1, h, w)  # [B, C, H, W]
        # 合并通道为1
        std_out = torch.mean(std_expanded, dim=1, keepdim=True)  # [B, 1, H, W]
        return std_out


class HA(nn.Module):
    """高效混合注意力：通道EMA+空间MCA优化版"""

    def __init__(self, channels, reduction=8, kernel_size=3):
        super().__init__()
        # ----------------- 通道分量（EMA改进） -----------------
        self.groups = max(1, channels // 64)  # 动态分组
        self.channel_weights = nn.Parameter(torch.ones(2))  # 方向权重

        # ----------------- 空间分量（MCA改进） -----------------
        self.spatial_conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size // 2, bias=False)
        self.std_pool = StdPool()  # 修改后的标准差池化

        # ----------------- 共享组件 -----------------
        self.gn = nn.GroupNorm(self.groups, channels)
        self.sigmoid = nn.Sigmoid()

    def _channel_attention(self, x):
        """改进的EMA通道注意力"""
        b, c, h, w = x.shape
        grouped = x.view(b * self.groups, -1, h, w)  # [B*g, C//g, H, W]

        # 方向感知池化
        x_h = F.adaptive_avg_pool2d(grouped, (h, 1))  # [B*g, C//g, H, 1]
        x_w = F.adaptive_avg_pool2d(grouped, (1, w))  # [B*g, C//g, 1, W]
        x_w = x_w.permute(0, 1, 3, 2)  # [B*g, C//g, W, 1]

        # 动态权重融合
        weights = torch.sigmoid(self.channel_weights)  # [2]
        fused = weights[0] * x_h + weights[1] * x_w  # [B*g, C//g, max(H,W), 1]

        # 分组归一化与残差
        fused = self.gn(fused)  # 增强特征稳定性
        return fused.view(b, c, *fused.shape[2:])  # [B, C, H, 1]

    def _spatial_attention(self, x):
        """改进的MCA空间注意力"""
        # 多模态池化
        avg_out = torch.mean(x, dim=1, keepdim=True)  # [B, 1, H, W]
        std_out = self.std_pool(x)  # [B, 1, H, W]
        spatial_feat = torch.cat([avg_out, std_out], dim=1)  # [B, 2, H, W]

        # 动态卷积增强
        att = self.spatial_conv(spatial_feat)  # [B, 1, H, W]
        return self.sigmoid(att)  # 空间权重图

    def forward(self, x):
        """前向传播"""
        # 通道注意力
        channel_att = self._channel_attention(x)  # [B, C, H, 1]

        # 空间注意力
        spatial_att = self._spatial_attention(x)  # [B, 1, H, W]

        # 联合注意力
        return x * channel_att * spatial_att  # [B, C, H, W]

class DMHAF(nn.Module):
    def __init__(self, in_channel, reduction_ratio=8):
        super().__init__()
        # 多模态特征融合
        self.fusion_gate = nn.Sequential(
            nn.Conv2d(in_channel * 2, in_channel // reduction_ratio, 1),
            nn.ReLU(),
            nn.Conv2d(in_channel // reduction_ratio, 3, 1),  # 生成3个融合权重
            nn.Softmax(dim=1)
        )
        # 注意力增强
        self.ha = HA(in_channel)

    def forward(self, img, depth):
        # 动态权重融合
        weights = self.fusion_gate(torch.cat([img, depth], dim=1))  # [B, 3, H, W]
        fused = weights[:, 0:1] * img + weights[:, 1:2] * depth + weights[:, 2:3] * (img * depth)

        # 注意力增强
        return self.ha(fused)

class BFNet(nn.Module):#改aspp 迭代次数
    def __init__(self, channel=32, kernel_size=3, reduction=4, bias=False, act=nn.PReLU(), n_resblocks=2, iteration=3):
        super(BFNet, self).__init__()

        self.backbone = pvt_v2_b2()  # [64, 128, 320, 512]
        path = _resolve_pvt_weight_path()
        save_model = _load_torch_checkpoint(str(path), map_location="cpu")
        model_dict = self.backbone.state_dict()
        state_dict = {k: v for k, v in save_model.items() if k in model_dict.keys()}
        model_dict.update(state_dict)
        self.backbone.load_state_dict(model_dict)

        self.iteration = iteration


        self.DCRP_4 = UnifiedCollaborativePyramid(64, 32, num_levels=2)
        self.DCRP_3 = UnifiedCollaborativePyramid(128, 32, num_levels=2)
        self.DCRP_2 = UnifiedCollaborativePyramid(320, 32, num_levels=2)
        self.DCRP_1 = UnifiedCollaborativePyramid(512, 32, num_levels=2)

        self.smar_4 = DMHAF(channel)
        self.smar_3 = DMHAF(channel)
        self.smar_2 = DMHAF(channel)
        self.smar_1 = DMHAF(channel)

        self.gate_1 = GGA(channel,channel)
        self.gate_2 = GGA(channel,channel)
        self.gate_3 = GGA(channel,channel)



        self.rfd_1 = FSRCB(channel, kernel_size, reduction, bias, act, n_resblocks)  # 32 x 22 x 22
        self.rfd_2 = FSRCB(2 * channel, kernel_size, reduction, bias, act, n_resblocks)  # 64 x 44 x 44
        self.rfd_3 = FSRCB(3 * channel, kernel_size, reduction, bias, act, n_resblocks)  # 96 x 88 x 88



        self.gate_conv = nn.Sequential(
            BasicConv2d(32, 1, 1),
            nn.Upsample(scale_factor=0.25, mode='bilinear', align_corners=True)
        )
        self.gate_conv_1 = BasicConv2d(32, 1, 1)
        self.gate_conv_2 = BasicConv2d(64, 1, 1)

        self.unsample_2 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)

        self.out = BasicConv2d(3 * channel, channel, 3, padding=1)
        self.pred = nn.Conv2d(channel, 1, 1)

        self.Fus = ASPP(2 * channel)
        self.downsample = nn.Upsample(scale_factor=0.5, mode='bilinear', align_corners=True)
        self.out_pred = nn.Conv2d(channel, 1, 1)

    def forward(self, x):  # 孪生网络，这里是batch拼接后的img和depth

        pvt = self.backbone(x)
        x4 = pvt[0]  # 64x176x176
        x3 = pvt[1]  # 128x88x88
        x2 = pvt[2]  # 320x44x44
        x1 = pvt[3]  # 512x22x22

        x4 = self.DCRP_4(x4)
        x3 = self.DCRP_3(x3)
        x2 = self.DCRP_2(x2)
        x1 = self.DCRP_1(x1)

        x4_img, x4_depth = torch.chunk(x4, 2, dim=0)
        x3_img, x3_depth = torch.chunk(x3, 2, dim=0)
        x2_img, x2_depth = torch.chunk(x2, 2, dim=0)
        x1_img, x1_depth = torch.chunk(x1, 2, dim=0)

        stage_pred = list()
        coarse_pred = None  # 阶段预测结果
        for iter in range(self.iteration):
            x1 = self.smar_1(x1_img, x1_depth)
            if coarse_pred == None:
                x1 = x1
            else:
                coarse_pred = self.gate_conv(coarse_pred)
                x1 = self.gate_1(x1, coarse_pred)
            x2_feed = self.rfd_1(x1)
            x2 = self.smar_2(x2_img, x2_depth)
            if iter > 0:
                x2_gate = self.unsample_2(self.gate_conv_1(x2_feed))
                x2 = self.gate_2(x2, x2_gate)
            x3_feed = self.rfd_2(torch.cat((x2, self.unsample_2(x2_feed)), dim=1))
            x3 = self.smar_3(x3_img, x3_depth)
            if iter > 0:
                x3_gate = self.unsample_2(self.gate_conv_2(x3_feed))
                x3 = self.gate_3(x3, x3_gate)
            x4_feed = self.rfd_3(torch.cat((x3, self.unsample_2(x3_feed)), dim=1))
            coarse_pred = self.out(x4_feed)
            out_map = self.pred(coarse_pred)
            pred = F.interpolate(out_map, scale_factor=8, mode='bilinear')
            stage_pred.append(pred)

        x4 = self.smar_4(x4_img, x4_depth)
        x4_out = self.downsample(x4)
        x_in = torch.cat((coarse_pred, x4_out), dim=1)
        refined_pred = self.Fus(x_in)

        pred2 = self.out_pred(refined_pred)
        final_pred = F.interpolate(pred2, scale_factor=8, mode='bilinear')
        return stage_pred, final_pred











