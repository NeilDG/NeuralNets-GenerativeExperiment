# -*- coding: utf-8 -*-
"""
Main entry for GAN training
Created on Sun Apr 19 13:22:06 2020

@author: delgallegon
"""

from __future__ import print_function
import os
import sys
import logging
from optparse import OptionParser
import random
import torch
import torch.nn.parallel
import torch.utils.data
import torchvision.utils as vutils
import numpy as np
import matplotlib.pyplot as plt
from torch.utils.tensorboard import SummaryWriter
from loaders import dataset_loader
from trainers import multistyle_net_trainer
import constants
from utils import logger
     
parser = OptionParser()
parser.add_option('--img_to_load', type=int, help="Image to load?", default=-1)

print = logger.log

def main(argv):
    (opts, args) = parser.parse_args(argv)
    logger.clear_log()
    print("=========BEGIN============")
    print("Is Coare? %d Has GPU available? %d Count: %d" % (constants.is_coare, torch.cuda.is_available(), torch.cuda.device_count()))
    print("Torch CUDA version: %s" % torch.version.cuda)
    
    manualSeed = random.randint(1, 10000) # use if you want new results
    random.seed(manualSeed)
    torch.manual_seed(manualSeed)
    
    device = torch.device("cuda:0" if (torch.cuda.is_available()) else "cpu")
    print("Device: %s" % device)
    writer = SummaryWriter('train_plot')
    
    gt = multistyle_net_trainer.MultiStyleTrainer(constants.STYLE_GAN_VERSION, constants.STYLE_ITERATION, device, writer)
    start_epoch = 0
    
    if(True): 
        checkpoint = torch.load(constants.STYLE_CHECKPATH)
        start_epoch = checkpoint['epoch'] + 1          
        gt.load_saved_state(checkpoint, constants.GENERATOR_KEY, constants.OPTIMIZER_KEY)
 
        print("Loaded checkpt: %s Current epoch: %d" % (constants.STYLE_CHECKPATH, start_epoch))
        print("===================================================")
    
    # Create the dataloader
    dataloader = dataset_loader.load_msg_dataset(constants.batch_size, opts.img_to_load)
    
    # Plot some training images
    if(constants.is_coare == 0):
        name_batch, vemon_batch_orig, gta_batch_orig = next(iter(dataloader))
        plt.figure(figsize=(constants.FIG_SIZE,constants.FIG_SIZE))
        plt.axis("off")
        plt.title("Training - Normal Images")
        plt.imshow(np.transpose(vutils.make_grid(vemon_batch_orig.to(device)[:constants.batch_size], nrow = 8, padding=2, normalize=True).cpu(),(1,2,0)))
        plt.show()
        
        plt.figure(figsize=(constants.FIG_SIZE,constants.FIG_SIZE))
        plt.axis("off")
        plt.title("Training - Topdown Images")
        plt.imshow(np.transpose(vutils.make_grid(gta_batch_orig.to(device)[:constants.batch_size], nrow = 8, padding=2, normalize=True).cpu(),(1,2,0)))
        plt.show()
    
    print("Starting Training Loop...")
    for epoch in range(start_epoch, constants.num_epochs):
        # For each batch in the dataloader
        for i, (name, vemon_batch, gta_batch) in enumerate(dataloader, 0):
            vemon_tensor = vemon_batch.to(device)
            gta_tensor = gta_batch.to(device)
            gt.train(vemon_tensor, gta_tensor, i)
        
        if(constants.is_coare == 0):
            gt.verify(vemon_batch_orig.to(device), gta_batch_orig.to(device)) #produce image from first batch
            gt.report(epoch)
        
        #save every X epoch
        gt.save_states(epoch, constants.STYLE_CHECKPATH, constants.GENERATOR_KEY, constants.OPTIMIZER_KEY)

#FIX for broken pipe num_workers issue.
if __name__=="__main__": 
    main(sys.argv)
