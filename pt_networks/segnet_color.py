
import torch
import torch.nn as nn
import torch.nn.functional as F




class Segnet(nn.Module):
    """A class for the segnet network with colorisation."""
    def __init__(self):

        super().__init__()

        self.layer_10 = self.conv2d_layer(1,64) #CHANGE 3 to in channels
        self.layer_11=self.conv2d_layer(64,64)

        self.layer_20=self.conv2d_layer(64,128)
        self.layer_21=self.conv2d_layer(128,128)

        self.layer_30=self.conv2d_layer(128,256)
        self.layer_31=self.conv2d_layer(256,256)
        self.layer_32=self.conv2d_layer(256,256)

        self.layer_40=self.conv2d_layer(256,512)
        self.layer_41=self.conv2d_layer(512,512)
        self.layer_42=self.conv2d_layer(512,512)

        self.layer_50=self.conv2d_layer(512,512)
        self.layer_51=self.conv2d_layer(512,512)
        self.layer_52=self.conv2d_layer(512,512)

        self.downsample= nn.MaxPool2d(2, stride=2, return_indices=True) 

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

        self.color_1=self.conv2d_layer(64,64)
        self.color_2=self.conv2d_layer(64,2)


        self.upsample = nn.MaxUnpool2d(2, stride=2) 
        self.linear_c_0=nn.Linear(512*8*8,64)
        self.linear_c_1=nn.Linear(64,2)

        self.linear_b_0=nn.Linear(512*8*8,64)
        self.linear_b_1=nn.Linear(64,4)
        self.flat=nn.Flatten()

    def vgg16_init(self, vgg16):
        """A function for initialisation of the vgg16 model."""
        
        original_layers=  [self.layer_10,self.layer_11,self.layer_20,self.layer_21
                           ,self.layer_30,self.layer_31,self.layer_32
                           ,self.layer_40,self.layer_41,self.layer_42
                           ,self.layer_50,self.layer_51,self.layer_52]

        layers = list(vgg16.features.children()) #Getting all features of vgg 

        vgg_layers = []
        for layer in layers:
            if isinstance(layer, nn.Conv2d):
                vgg_layers.append(layer)

        SegnetEnc=[]

        for layer in original_layers:
            
            for l in layer: #loop through sequential
             if isinstance(l, nn.Conv2d):
                SegnetEnc.append(l)

      
        assert len(vgg_layers) == len(SegnetEnc)

        i=0
        for layer1, layer2 in zip(vgg_layers, SegnetEnc):

            if i!=0: #Skipping first layer
             
             layer2.weight.data = layer1.weight.data
             layer2.bias.data = layer1.bias.data

    
            i+=1


    def conv2d_layer(self,in_ch,out_ch,kernel_size=3,padding=1,stride=1):
        """A function creating a layer consisting of convolution, batch normalisation and relu.
        Args:
            in_ch (int): Number of input channels.
            out_ch (int): Number of output channels.
            padding (int, optional): Padding for the convolution stage. Default is 1.
        
        Returns:
            A layer made up of three smaller layers.
        
        """

        layer=[]
        layer.append(nn.BatchNorm2d(in_ch))
        layer.append(nn.Conv2d(in_channels=in_ch,out_channels=out_ch,kernel_size=kernel_size,padding=padding,stride=stride))
        layer.append(nn.ReLU(inplace=True))

        return nn.Sequential(*layer)

    def forward(self,x):


        #print(x.shape)

       
        x=self.layer_10(x)
        x=self.layer_11(x)
        x,i1=self.downsample(x)
        x1=x.size()
        
        #print(x.shape)

        x=self.layer_20(x)
        x=self.layer_21(x)
        x,i2=self.downsample(x)
        x2=x.size()

        #print(x.shape)

        x=self.layer_30(x)
        x=self.layer_31(x)
        x=self.layer_32(x)
        x,i3=self.downsample(x)
        x3=x.size()

        #print(x.shape)

        x=self.layer_40(x)
        x=self.layer_41(x)
        x=self.layer_42(x)
        x,i4=self.downsample(x)
        x4=x.size()

        #print(x.shape)

        x=self.layer_50(x)
        x=self.layer_51(x)
        x=self.layer_52(x)
        x,i5=self.downsample(x)
        x5=x.size()

        flat=self.flat(x)
       # print(flat.size(),"flatsize")

        c_0=F.relu(self.linear_c_0(flat))
        c_= (self.linear_c_1(c_0))
        b_0=F.relu(self.linear_b_0(flat))
        b_=F.relu(self.linear_b_1(b_0))

       # print(x.shape)

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

        color_1=self.color_1(x)
        color_2=self.color_2(color_1)

        x=self.layer_11_t(x)
        x=self.layer_10_t(x)
        
        #print(x.shape)

        return c_,b_,x,color_2










    






        



   







        


