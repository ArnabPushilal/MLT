import torch
import torch.nn as nn
import torch.nn.functional as F

class SegNet(nn.Module):
    def __init__(self):
        super().__init__()
        filter = [64, 128, 256, 512, 512]

        # define encoder decoder layers
        self.encoder_block = nn.ModuleList([self.conv2d_layer(3, filter[0])])
        self.down_sampling = nn.MaxPool2d(kernel_size=2, stride=2, return_indices=True)

        for i in range(4):
            self.encoder_block.append(self.conv2d_layer(filter[i], filter[i + 1]))  

        # define convolution layer
        self.conv_block_enc = nn.ModuleList([self.conv2d_layer(filter[0], filter[0])])
        for i in range(4):
            if i == 0:
                self.conv_block_enc.append(self.conv2d_layer(filter[i + 1], filter[i + 1]))
            else:
                self.conv_block_enc.append(nn.Sequential(self.conv2d_layer(filter[i + 1], filter[i + 1]),
                                                         self.conv2d_layer(filter[i + 1], filter[i + 1])))

        # define task attention layers
        self.encoder_att = nn.ModuleList([nn.ModuleList([self.att_layer([filter[0], filter[0], filter[0]])])])
        self.encoder_block_att = nn.ModuleList([self.conv2d_layer(filter[0], filter[1])])

        for j in range(3):
            if j < 2:
                self.encoder_att.append(nn.ModuleList([self.att_layer([filter[0], filter[0], filter[0]])]))
            for i in range(4):
                self.encoder_att[j].append(self.att_layer([2 * filter[i + 1], filter[i + 1], filter[i + 1]]))

        for i in range(4):
            if i < 3:
                self.encoder_block_att.append(self.conv2d_layer(filter[i + 1], filter[i + 2]))
            else:
                self.encoder_block_att.append(self.conv2d_layer(filter[i + 1], filter[i + 1]))

        linear_class_layers = [nn.Linear(512*8*8,64),nn.ReLU(inplace=True),nn.Linear(64,2)]
        self.linear_class=nn.Sequential(*linear_class_layers)
        linear_bb_layers = [nn.Linear(512*8*8,64),nn.ReLU(inplace=True), nn.Linear(64,4)]
        self.linear_bb=nn.Sequential(*linear_bb_layers)
        self.decoder = Decoder()
        self.flat=nn.Flatten()
    
    def conv2d_layer(self,in_ch,out_ch,kernel_size=3,padding=1,stride=1):

        layer=[]
        layer.append(nn.BatchNorm2d(in_ch))
        layer.append(nn.Conv2d(in_channels=in_ch,out_channels=out_ch,kernel_size=kernel_size,padding=padding,stride=stride))
        layer.append(nn.ReLU(inplace=True))

        return nn.Sequential(*layer)

    def att_layer(self, channel):
        att_block = nn.Sequential(
            nn.Conv2d(in_channels=channel[0], out_channels=channel[1], kernel_size=1, padding=0),
            nn.BatchNorm2d(channel[1]),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels=channel[1], out_channels=channel[2], kernel_size=1, padding=0),
            nn.BatchNorm2d(channel[2]),
            nn.Sigmoid(),
        )
        return att_block

    def forward(self,x):
        g_encoder, g_maxpool,indices,x_shapes = ([0] * 5 for _ in range(4))
        for i in range(5):
            g_encoder[i] = [0] * 2 

      
        # define attention list for tasks
        atten_encoder, atten_decoder = ([0] * 3 for _ in range(2))  
        for i in range(3):
            atten_encoder[i], atten_decoder[i] = ([0] * 5 for _ in range(2))
        for i in range(3):
            for j in range(5):
                atten_encoder[i][j], atten_decoder[i][j] = ([0] * 3 for _ in range(2))
        
        # define global shared network
        for i in range(5):
            if i == 0:
                g_encoder[i][0] = self.encoder_block[i](x)
                g_encoder[i][1] = self.conv_block_enc[i](g_encoder[i][0])
                
                g_maxpool[i], indices[i] = self.down_sampling(g_encoder[i][1])
                x_shapes[i] = g_maxpool[i].size()
            else:
                g_encoder[i][0] = self.encoder_block[i](g_maxpool[i - 1])
                g_encoder[i][1] = self.conv_block_enc[i](g_encoder[i][0])             
                g_maxpool[i], indices[i] = self.down_sampling(g_encoder[i][1])
                x_shapes[i] = g_maxpool[i].size()

        for i in range(3):
            for j in range(5):
                if j == 0:
                    atten_encoder[i][j][0] = self.encoder_att[i][j](g_encoder[j][0])
                    atten_encoder[i][j][1] = (atten_encoder[i][j][0]) * g_encoder[j][1]
                    atten_encoder[i][j][2] = self.encoder_block_att[j](atten_encoder[i][j][1])
                    atten_encoder[i][j][2] = F.max_pool2d(atten_encoder[i][j][2], kernel_size=2, stride=2)
                else:
                    atten_encoder[i][j][0] = self.encoder_att[i][j](torch.cat((g_encoder[j][0], atten_encoder[i][j - 1][2]), dim=1))
                    atten_encoder[i][j][1] = (atten_encoder[i][j][0]) * g_encoder[j][1]
                    atten_encoder[i][j][2] = self.encoder_block_att[j](atten_encoder[i][j][1])
                    atten_encoder[i][j][2] = F.max_pool2d(atten_encoder[i][j][2], kernel_size=2, stride=2)
        
        x = atten_encoder[0][-1][-1].shape   
        y = atten_encoder[1][-1][-1].shape   
        z = atten_encoder[2][-1][-1].shape     

        target_pred = self.decoder(atten_encoder[0][-1][-1],indices,x_shapes)
        flat_c = self.flat(atten_encoder[1][-1][-1])
        flat_bb = self.flat(atten_encoder[2][-1][-1])
        aux_pred_c = self.linear_class(flat_c)
        aux_pred_bb = self.linear_bb(flat_bb)
        print("aux_pred_bb",aux_pred_bb.shape)
        print("aux_pred_c",aux_pred_c.shape)
        print("target_pred",target_pred.shape)

        return aux_pred_c,aux_pred_bb, target_pred
        

class Decoder(nn.Module):

    def __init__(self):

        super().__init__()
        self.layer_52_t=self.conv2d_layer(512,512)
        self.layer_51_t=self.conv2d_layer(512,512)
        self.layer_50_t=self.conv2d_layer(512,512)

        
        self.layer_42_t=self.conv2d_layer(512,512)
        self.layer_41_t=self.conv2d_layer(512,512)
        self.layer_40_t=self.conv2d_layer(512,256)

        self.layer_32_t=self.conv2d_layer(256,256)
        self.layer_31_t=self.conv2d_layer(256,256)
        self.layer_30_t=self.conv2d_layer(256,128)

        self.layer_21_t=self.conv2d_layer(128,128)
        self.layer_20_t=self.conv2d_layer(128,64)

    
        self.layer_11_t=self.conv2d_layer(64,64)
        self.layer_10_t=self.conv2d_layer(64,2) 

        self.upsample = nn.MaxUnpool2d(2, stride=2)


    def conv2d_layer(self,in_ch,out_ch,kernel_size=3,padding=1,stride=1):

        layer=[]
        layer.append(nn.BatchNorm2d(in_ch))
        layer.append(nn.Conv2d(in_channels=in_ch,out_channels=out_ch,kernel_size=kernel_size,padding=padding,stride=stride))
        layer.append(nn.ReLU(inplace=True))

        return nn.Sequential(*layer)

    def forward(self,x,indices,x_shapes):
        i1,i2,i3,i4,i5 = indices
        x1,x2,x3,x4,x5 = x_shapes
                    
        #print(x.shape)

       
    #     x=self.layer_10(x)
    #     x=self.layer_11(x)
    #     x,i1=self.downsample(x)
    #     x1=x.size()
        
    #     #print(x.shape)

    #     x=self.layer_20(x)
    #     x=self.layer_21(x)
    #     x,i2=self.downsample(x)
    #     x2=x.size()

    #     #print(x.shape)

    #     x=self.layer_30(x)
    #     x=self.layer_31(x)
    #     x=self.layer_32(x)
    #     x,i3=self.downsample(x)
    #     x3=x.size()

    #     #print(x.shape)

    #     x=self.layer_40(x)
    #     x=self.layer_41(x)
    #     x=self.layer_42(x)
    #     x,i4=self.downsample(x)
    #     x4=x.size()

    #     #print(x.shape)

    #     x=self.layer_50(x)
    #     x=self.layer_51(x)
    #     x=self.layer_52(x)
    #     x,i5=self.downsample(x)
    #     x5=x.size()

    #     flat=self.flat(x)
    #    # print(flat.size(),"flatsize")

    #     c_0=F.relu(self.linear_c_0(flat))
    #     c_= (self.linear_c_1(c_0))
    #     b_0=F.relu(self.linear_b_0(flat))
    #     b_=F.relu(self.linear_b_1(b_0))

    #    # print(x.shape)

        x=self.upsample(x,i5,output_size=x4)
        x=self.layer_52_t(x)
        x=self.layer_51_t(x)
        x=self.layer_50_t(x)
   
        #print(x.shape)

        x=self.upsample(x,i4,output_size=x3)
        x=self.layer_42_t(x)
        x=self.layer_41_t(x)
        x=self.layer_40_t(x)

       # print(x.shape)

        x=self.upsample(x,i3,output_size=x2)
        x=self.layer_32_t(x)
        x=self.layer_31_t(x)
        x=self.layer_30_t(x)

        #print(x.shape)

        x=self.upsample(x,i2,output_size=x1)
        x=self.layer_21_t(x)
        x=self.layer_20_t(x)


        #print(x.shape)

        
        x=self.upsample(x,i1)
        x=self.layer_11_t(x)
        x=self.layer_10_t(x)
        
        #print(x.shape)

        return x

segnet = SegNet()
print(segnet) 
# class Segnet(nn.Module):

#     def __init__(self):

#         super().__init__()

#         self.encoder= Encoder()
#         self.flat=nn.Flatten()
#         self.linear_c_0=nn.Linear(128*256*256,64)
#         self.linear_c_1=nn.Linear(64,2)

#         self.linear_b_0=nn.Linear(128*256*256,64)
#         self.linear_b_1=nn.Linear(64,4)
#         self.decoder= Decoder()

 


#     def forward(self,x):

#         enc=self.encoder(x)
#         #print(enc.size(),"encsize")
#         flat=self.flat(enc)
#        # print(flat.size(),"flatsize")

#         c_0=F.relu(self.linear_c_0(flat))
#         c_= (self.linear_c_1(c_0))
#         b_0=F.relu(self.linear_b_0(flat))
#         b_=F.relu(self.linear_b_1(b_0))
#         dec=self.decoder(enc)

#         return c_,b_,dec

# class AttentionBlock(nn.Module):

#     def __init__(self,in_channel,inter_channel,out_channel,features,in_channel_3,out_channel_3):

#         """
#         @params:
#         features: Shared features (From the 3rd or so conv) to be multiplied element-wise
#         in_channel: Number of in_channels for 1st 1x1 conv
#         inter_channel: Intermediate channels for 2nd 1x1 conv
#         out_channels: Out channels for 2nd 1x1 conv
        
#         in_channel_3: In channels for 3x3 conv
#         out_channel_3: Out channels for 3x3 conv


        
#         """

#         super().__init__()

#         self.attention_weights= self.attention(in_channel,inter_channel,out_channel)
#         self.features=features
#         self.conv2d_layer=self.conv2d_layer(in_channel_3,out_channel_3)

#     def conv2d_layer(self,in_ch,out_ch,kernel_size=3,padding=1,stride=1):

#         layer=[]
#         layer.append(nn.BatchNorm2d(in_ch))
#         layer.append(nn.Conv2d(in_channels=in_ch,out_channels=out_ch,kernel_size=kernel_size,padding=padding,stride=stride))
#         layer.append(nn.ReLU(inplace=True))
#         return nn.Sequential(*layer)


#     def attention_(self,in_channel,inter_channel,out_channel):

#         layer=[]
         
#         layer.append(nn.Conv2d(in_channels=in_channel, out_channels=out_channel, kernel_size=1, padding=0))
#         layer.append(nn.BatchNorm2d(inter_channel))
#         layer.append(nn.ReLU(inplace=True))
#         layer.append(nn.Conv2d(in_channels=in_channel, out_channels=inter_channel, kernel_size=1, padding=0))
#         layer.append(nn.BatchNorm2d(out_channel))
#         layer.append(nn.Sigmoid())
        
#         return nn.Sequential(*layer)

#     def forward(self,x):

#         x=self.attention_weights(x)
#         x=x*self.features
#         x=self.conv2d_layer(x)





    






        



   







        


