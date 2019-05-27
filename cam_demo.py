from __future__ import division
import time
import torch 
import torch.nn as nn
from torch.autograd import Variable
import numpy as np
import cv2 
from util import *
from darknet import Darknet
from preprocess import prep_image, inp_to_image
import pandas as pd
import random 
import argparse
import pickle as pkl


def prep_image(img, inp_dim):
    """
    Prepare image for inputting to the neural network. 
    
    Returns a Variable 
    """

    orig_im = img
    dim = orig_im.shape[1], orig_im.shape[0]
    img = cv2.resize(orig_im, (inp_dim, inp_dim))
    img_ = img[:,:,::-1].transpose((2,0,1)).copy()
    img_ = torch.from_numpy(img_).float().div(255.0).unsqueeze(0)
    return img_, orig_im, dim

def write(x, img):
    c1 = tuple(x[1:3].int())
    c2 = tuple(x[3:5].int())
    cls = int(x[-1])
    print(str(cls))
    label = "{0}".format(classes[cls])
    color = random.choice(colors)
    cv2.rectangle(img, c1, c2,color, 1)
    t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 1 , 1)[0]
    c2 = c1[0] + t_size[0] + 3, c1[1] + t_size[1] + 4
    cv2.rectangle(img, c1, c2,color, -1)
    cv2.putText(img, label, (c1[0], c1[1] + t_size[1] + 4), cv2.FONT_HERSHEY_PLAIN, 1, [225,255,255], 1);
    return img

def object_li(x):
        cls = int(x[-1])
        return cls

def arg_parse():
    """
    Parse arguements to the detect module
    
    """    
    parser = argparse.ArgumentParser(description='YOLO v3 Cam Demo')
    parser.add_argument("--confidence", dest = "confidence", help = "Object Confidence to filter predictions", default = 0.05)
    parser.add_argument("--nms_thresh", dest = "nms_thresh", help = "NMS Threshhold", default = 0.4)
    parser.add_argument("--reso", dest = 'reso', help = 
                        "Input resolution of the network. Increase to increase accuracy. Decrease to increase speed",
                        default = "160", type = str)
    return parser.parse_args()

if __name__ == '__main__':
    cfgfile = "cfg/yolov3-custom.cfg" #change cfg cfg/yolov3.cfg→cfg/yolov3-custom.cfg
    weightsfile = "weights/yolov3_ckpt_24.pth" #change model
    num_classes = 1 #80->1

    temp = 0
    ch_num = 0

    args = arg_parse()
    confidence = float(args.confidence)
    nms_thesh = float(args.nms_thresh)
    start = 0
    CUDA = torch.cuda.is_available()
        
    num_classes = 1 #80->1
    bbox_attrs = 5 + num_classes
    
    model = Darknet(cfgfile)
    if weightsfile.endswith(".weights"):
        # Load darknet weights
        model.load_darknet_weights(weightsfile)
    else:
        if CUDA:
            # Load .pth file
            model.load_state_dict(torch.load(weightsfile)) #load .pth file
            print('gpu')
        else:
            # gpu model load on cpu only computer
            model.load_state_dict(torch.load(weightsfile, map_location=lambda storage, loc: storage))
            print('cpu')

    #model.load_weights(weightsfile)
    
    model.net_info["height"] = args.reso
    inp_dim = int(model.net_info["height"])
    
    assert inp_dim % 32 == 0 
    assert inp_dim > 32

    if CUDA:
        model.cuda()
            
    model.eval()
    
    URL = "rtsp://admin:nsg888888@140.130.93.152:554/cam/realmonitor?channel=3&subtype=0"
    cap = cv2.VideoCapture(URL)
    
    assert cap.isOpened(), 'Cannot capture source'
    
    frames = 0
    start = time.time()    

    fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
    fps = 24
    savedPath = './saveT.avi'
    ret, frame = cap.read()
    out = cv2.VideoWriter(savedPath, fourcc, fps, (frame.shape[1], frame.shape[0]))
    while cap.isOpened():
        
        ret, frame = cap.read()
        if ret:
            
            img, orig_im, dim = prep_image(frame, inp_dim)               
            im_dim = torch.FloatTensor(dim).repeat(1,2)

            if CUDA:
                im_dim = im_dim.cuda()
                img = img.cuda()            
            
            output = model(Variable(img), CUDA)
            output = write_results(output, confidence, num_classes, nms = True, nms_conf = nms_thesh)

            if type(output) == int:
                frames += 1
                print("FPS of the video is {:5.2f}".format( frames / (time.time() - start)))
                #out.write(frame)
                cv2.imshow("frame",orig_im)
                key = cv2.waitKey(1)
                if key & 0xFF == ord('q'):
                    break
                continue
        
            output[:,1:5] = torch.clamp(output[:,1:5], 0.0, float(inp_dim))/inp_dim
            
            output[:,[1,3]] *= frame.shape[1]
            output[:,[2,4]] *= frame.shape[0]
            
            classes = load_classes('data/chicken.names') #coco.names->chicken.names
            colors = pkl.load(open("pallete", "rb"))
            
            ch_li = list(map(lambda x: object_li(x),output))
            ch_num = ch_li.count(14)
            if temp < ch_num:
                temp = ch_num
            list(map(lambda x: write(x, orig_im), output))
            
            cv2.putText(orig_im, str(temp), (30,50), cv2.FONT_HERSHEY_PLAIN, 3, [255,255,255], 5)
            #out.write(frame)
            cv2.imshow("frame",orig_im)
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q'):
                break
            frames += 1
            print("FPS of the video is {:5.2f}".format( frames / (time.time() - start)))
            
        else:
            break
    
    

