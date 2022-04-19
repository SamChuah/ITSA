import torch.nn.functional as F
import torch.utils.data
from models.GwcNet.submodules import *
import math

class feature_extraction(nn.Module):
    def __init__(self, concat_feature=False, concat_feature_channel=12):
        super(feature_extraction, self).__init__()
        self.concat_feature = concat_feature

        self.inplanes = 32
        self.firstconv = nn.Sequential(convbn(3, 32, 3, 2, 1, 1),
                                       nn.ReLU(inplace=True),
                                       convbn(32, 32, 3, 1, 1, 1),
                                       nn.ReLU(inplace=True),
                                       convbn(32, 32, 3, 1, 1, 1),
                                       nn.ReLU(inplace=True))

        self.layer1 = self._make_layer(BasicBlock, 32, 3, 1, 1, 1)
        self.layer2 = self._make_layer(BasicBlock, 64, 16, 2, 1, 1)
        self.layer3 = self._make_layer(BasicBlock, 128, 3, 1, 1, 1)
        self.layer4 = self._make_layer(BasicBlock, 128, 3, 1, 1, 2)

        if self.concat_feature:
            self.lastconv = nn.Sequential(convbn(320, 128, 3, 1, 1, 1),
                                          nn.ReLU(inplace=True),
                                          nn.Conv2d(128, concat_feature_channel, kernel_size=1, padding=0, stride=1,
                                                    bias=False))

    def _make_layer(self, block, planes, blocks, stride, pad, dilation):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion,
                          kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion), )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, pad, dilation))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes, 1, None, pad, dilation))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.firstconv(x)
        x = self.layer1(x)
        l2 = self.layer2(x)
        l3 = self.layer3(l2)
        l4 = self.layer4(l3)

        gwc_feature = torch.cat((l2, l3, l4), dim=1)

        if not self.concat_feature:
            return {"gwc_feature": gwc_feature}
        else:
            concat_feature = self.lastconv(gwc_feature)
            return {"gwc_feature": gwc_feature, "concat_feature": concat_feature}


class hourglass(nn.Module):
    def __init__(self, in_channels):
        super(hourglass, self).__init__()

        self.conv1 = nn.Sequential(convbn_3d(in_channels, in_channels * 2, 3, 2, 1),
                                   nn.ReLU(inplace=True))

        self.conv2 = nn.Sequential(convbn_3d(in_channels * 2, in_channels * 2, 3, 1, 1),
                                   nn.ReLU(inplace=True))

        self.conv3 = nn.Sequential(convbn_3d(in_channels * 2, in_channels * 4, 3, 2, 1),
                                   nn.ReLU(inplace=True))

        self.conv4 = nn.Sequential(convbn_3d(in_channels * 4, in_channels * 4, 3, 1, 1),
                                   nn.ReLU(inplace=True))

        self.conv5 = nn.Sequential(
            nn.ConvTranspose3d(in_channels * 4, in_channels * 2, 3, padding=1, output_padding=1, stride=2, bias=False),
            nn.BatchNorm3d(in_channels * 2))

        self.conv6 = nn.Sequential(
            nn.ConvTranspose3d(in_channels * 2, in_channels, 3, padding=1, output_padding=1, stride=2, bias=False),
            nn.BatchNorm3d(in_channels))

        self.redir1 = convbn_3d(in_channels, in_channels, kernel_size=1, stride=1, pad=0)
        self.redir2 = convbn_3d(in_channels * 2, in_channels * 2, kernel_size=1, stride=1, pad=0)

    def forward(self, x):
        conv1 = self.conv1(x)
        conv2 = self.conv2(conv1)

        conv3 = self.conv3(conv2)
        conv4 = self.conv4(conv3)

        conv5 = F.relu(self.conv5(conv4) + self.redir2(conv2), inplace=True)
        conv6 = F.relu(self.conv6(conv5) + self.redir1(x), inplace=True)

        return conv6


class GwcNet(nn.Module):
    def __init__(self, maxdisp, eps=0.1, use_concat_volume=False, itsa=False):
        super(GwcNet, self).__init__()
        self.maxdisp = maxdisp
        self.use_concat_volume = use_concat_volume
        self.itsa = itsa
        self.eps = eps

        self.num_groups = 40

        if self.use_concat_volume:
            self.concat_channels = 12
            self.feature_extraction = feature_extraction(concat_feature=True,
                                                         concat_feature_channel=self.concat_channels)
        else:
            self.concat_channels = 0
            self.feature_extraction = feature_extraction(concat_feature=False)

        self.dres0 = nn.Sequential(convbn_3d(self.num_groups + self.concat_channels * 2, 32, 3, 1, 1),
                                   nn.ReLU(inplace=True),
                                   convbn_3d(32, 32, 3, 1, 1),
                                   nn.ReLU(inplace=True))

        self.dres1 = nn.Sequential(convbn_3d(32, 32, 3, 1, 1),
                                   nn.ReLU(inplace=True),
                                   convbn_3d(32, 32, 3, 1, 1))

        self.dres2 = hourglass(32)

        self.dres3 = hourglass(32)

        self.dres4 = hourglass(32)

        self.classif0 = nn.Sequential(convbn_3d(32, 32, 3, 1, 1),
                                      nn.ReLU(inplace=True),
                                      nn.Conv3d(32, 1, kernel_size=3, padding=1, stride=1, bias=False))

        self.classif1 = nn.Sequential(convbn_3d(32, 32, 3, 1, 1),
                                      nn.ReLU(inplace=True),
                                      nn.Conv3d(32, 1, kernel_size=3, padding=1, stride=1, bias=False))

        self.classif2 = nn.Sequential(convbn_3d(32, 32, 3, 1, 1),
                                      nn.ReLU(inplace=True),
                                      nn.Conv3d(32, 1, kernel_size=3, padding=1, stride=1, bias=False))

        self.classif3 = nn.Sequential(convbn_3d(32, 32, 3, 1, 1),
                                      nn.ReLU(inplace=True),
                                      nn.Conv3d(32, 1, kernel_size=3, padding=1, stride=1, bias=False))

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.Conv3d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.kernel_size[2] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm3d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.Linear):
                m.bias.data.zero_()
                
    def cost_regularization(self, cost):
        cost0 = self.dres0(cost)
        cost0 = self.dres1(cost0) + cost0

        out1 = self.dres2(cost0)
        out2 = self.dres3(out1)
        out3 = self.dres4(out2)

        if self.training:
            cost0 = self.classif0(cost0)
            cost1 = self.classif1(out1)
            cost2 = self.classif2(out2)
            cost3 = self.classif3(out3)

            cost0 = F.interpolate(cost0, scale_factor=4, mode='trilinear', align_corners=False)
            cost0 = torch.squeeze(cost0, 1)
            pred0 = F.softmax(cost0, dim=1)
            pred0 = disparity_regression(pred0, self.maxdisp)

            cost1 = F.interpolate(cost1, scale_factor=4, mode='trilinear', align_corners=False)
            cost1 = torch.squeeze(cost1, 1)
            pred1 = F.softmax(cost1, dim=1)
            pred1 = disparity_regression(pred1, self.maxdisp)

            cost2 = F.interpolate(cost2, scale_factor=4, mode='trilinear', align_corners=False)
            cost2 = torch.squeeze(cost2, 1)
            pred2 = F.softmax(cost2, dim=1)
            pred2 = disparity_regression(pred2, self.maxdisp)

            cost3 = F.interpolate(cost3, scale_factor=4, mode='trilinear', align_corners=False)
            cost3 = torch.squeeze(cost3, 1)
            pred3 = F.softmax(cost3, dim=1)
            pred3 = disparity_regression(pred3, self.maxdisp)
            
            return [pred0, pred1, pred2, pred3]

        else:
            cost3 = self.classif3(out3)
            cost3 = F.interpolate(cost3, scale_factor=4, mode='trilinear', align_corners=False)
            cost3 = torch.squeeze(cost3, 1)
            pred3 = F.softmax(cost3, dim=1)
            pred3 = disparity_regression(pred3, self.maxdisp)
            
            return pred3
            
                    
    def clip(self, img, img_min=None, img_max=None):
        if img_min is None:
            img_min = torch.tensor([-2.1179, -2.0357, -1.8044]).view(1,3,1,1).cuda()

        if img_max is None:
            img_max = torch.tensor([2.2489, 2.4286, 2.6400]).view(3,1,1).cuda()

        img = torch.clip(img, min=img_min, max=img_max)
        
        return img
        
            
    def grad_norm(self, grad):
        grad = grad.pow(2)
        grad = F.normalize(grad, p=2, dim=1) 
        grad = grad * self.eps
        return grad
        

    def forward(self, imgL, imgR):
        if self.itsa:
            #=================================================#
            # SCP Augmentation 
            imgL_ = imgL.clone().detach()
            imgL_.requires_grad = True 
            
            imgR_ = imgR.clone().detach() 
            imgR_.requires_grad = True 
            
            self.eval() 
            featL_ = self.feature_extraction(imgL_)
            gradL = torch.autograd.grad(outputs=featL_["gwc_feature"], inputs=imgL_, grad_outputs=torch.ones_like(featL_["gwc_feature"]), create_graph=False)
            gradL = gradL[0].clone().detach()  # B,C,H,W
            
            featR_ = self.feature_extraction(imgR_)
            gradR = torch.autograd.grad(outputs=featR_["gwc_feature"], inputs=imgR_, grad_outputs=torch.ones_like(featR_["gwc_feature"]), create_graph=False)
            gradR = gradR[0].clone().detach()  # B,C,H,W
            
            gradL = self.grad_norm(gradL)
            gradR = self.grad_norm(gradR)
            
            imgL_scp = imgL.clone().detach() + gradL
            imgR_scp = imgR.clone().detach() + gradR
            
            imgL_scp = self.clip(imgL_scp).detach()
            imgR_scp = self.clip(imgR_scp).detach()
            
            del imgL_, imgR_             
            self.train()
            
            # Forward Pass
            featL_scp = self.feature_extraction(imgL_scp)
            featR_scp = self.feature_extraction(imgR_scp)
            
            featL = self.feature_extraction(imgL)
            featR = self.feature_extraction(imgR) 
               
            gwc_volume = build_gwc_volume(featL_scp["gwc_feature"], featR_scp["gwc_feature"], self.maxdisp // 4,
                                          self.num_groups)
            if self.use_concat_volume:
                concat_volume = build_concat_volume(featL_scp["concat_feature"], featR_scp["concat_feature"],
                                                    self.maxdisp // 4)
                volume = torch.cat((gwc_volume, concat_volume), 1)
            else:
                volume = gwc_volume
                  
            dispEsts = self.cost_regularization(volume)
          
            featEsts = {"left": featL["gwc_feature"],
                        "right": featR["gwc_feature"],
                        "left_scp": featL_scp["gwc_feature"],
                        "right_scp": featR_scp["gwc_feature"]}
            
            return featEsts, dispEsts
        else:
            featL = self.feature_extraction(imgL)
            featR = self.feature_extraction(imgR) 
               
            gwc_volume = build_gwc_volume(featL["gwc_feature"], featR["gwc_feature"], self.maxdisp // 4,
                                          self.num_groups)
            if self.use_concat_volume:
                concat_volume = build_concat_volume(featL["concat_feature"], featR["concat_feature"],
                                                    self.maxdisp // 4)
                volume = torch.cat((gwc_volume, concat_volume), 1)
            else:
                volume = gwc_volume
                  
            dispEsts = self.cost_regularization(volume)
            
            return dispEsts


def GwcNet_G(d, eps=1.0, itsa=False):
    return GwcNet(d, eps=eps, use_concat_volume=False, itsa=itsa)


def GwcNet_GC(d, eps=1.0, itsa=False):
    return GwcNet(d, eps=eps, use_concat_volume=True, itsa=itsa)
