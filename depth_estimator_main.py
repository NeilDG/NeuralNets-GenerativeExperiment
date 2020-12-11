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
from loaders import dataset_loader
from trainers import depth_trainer
import constants

parser = OptionParser()
parser.add_option('--coare', type=int, help="Is running on COARE?", default=0)
parser.add_option('--img_to_load', type=int, help="Image to load?", default=-1)
parser.add_option('--load_previous', type=int, help="Load previous?", default=0)
parser.add_option('--iteration', type=int, help="Style version?", default="1")
parser.add_option('--adv_weight', type=float, help="Weight", default="1.0")
parser.add_option('--likeness_weight', type=float, help="Weight", default="10.0")
parser.add_option('--brightness_enhance', type=float, help="Weight", default="1.00")
parser.add_option('--contrast_enhance', type=float, help="Weight", default="1.00")
parser.add_option('--g_lr', type=float, help="LR", default="0.0002")
parser.add_option('--d_lr', type=float, help="LR", default="0.0002")


# --img_to_load=-1 --load_previous=1
# Update config if on COARE
def update_config(opts):
    constants.is_coare = opts.coare
    constants.brightness_enhance = opts.brightness_enhance
    constants.contrast_enhance = opts.contrast_enhance

    if (constants.is_coare == 1):
        print("Using COARE configuration.")
        constants.batch_size = 1024

        constants.ITERATION = str(opts.iteration)
        constants.COLOR_TRANSFER_CHECKPATH = 'checkpoint/' + constants.COLOR_TRANSFER_VERSION + "_" + constants.ITERATION + '.pt'

        constants.DATASET_NOISY_GTA_PATH = "/scratch1/scratch2/neil.delgallego/Noisy GTA/noisy/"
        constants.DATASET_CLEAN_GTA_PATH = "/scratch1/scratch2/neil.delgallego/Noisy GTA/clean/"
        constants.DATASET_VEMON_PATH_COMPLETE = "/scratch1/scratch2/neil.delgallego/VEMON Dataset/frames/"
        constants.DATASET_DIV2K_PATH = "/scratch1/scratch2/neil.delgallego/Div2k_Patch Dataset Enhanced/"
        constants.DATASET_HAZY_PATH_COMPLETE = "/scratch1/scratch2/neil.delgallego/Synth Hazy/hazy/"
        constants.DATASET_CLEAN_PATH_COMPLETE = "/scratch1/scratch2/neil.delgallego/Synth Hazy/clean/"

        constants.DATASET_IHAZE_PATH_PATCH = "/scratch1/scratch2/neil.delgallego/RESIDE - Patch/"
        constants.DATASET_HAZY_PATH_PATCH = "/scratch1/scratch2/neil.delgallego/Synth Hazy - Patch/hazy/"
        constants.DATASET_CLEAN_PATH_PATCH = "/scratch1/scratch2/neil.delgallego/Synth Hazy - Patch/clean/"
        constants.DATASET_HAZY_TEST_PATH_2 = "/scratch1/scratch2/neil.delgallego/Synth Hazy/clean/"

        constants.num_workers = 4


def show_images(img_tensor, caption):
    device = torch.device("cuda:0" if (torch.cuda.is_available()) else "cpu")
    plt.figure(figsize=constants.FIG_SIZE)
    plt.axis("off")
    plt.title(caption)
    plt.imshow(np.transpose(
        vutils.make_grid(img_tensor.to(device)[:constants.batch_size], nrow=8, padding=2, normalize=True).cpu(),
        (1, 2, 0)))
    plt.show()


def main(argv):
    (opts, args) = parser.parse_args(argv)
    update_config(opts)
    print("=====================BEGIN============================")
    print("Is Coare? %d Has GPU available? %d Count: %d" % (
    constants.is_coare, torch.cuda.is_available(), torch.cuda.device_count()))
    print("Torch CUDA version: %s" % torch.version.cuda)

    manualSeed = random.randint(1, 10000)  # use if you want new results
    random.seed(manualSeed)
    torch.manual_seed(manualSeed)

    device = torch.device("cuda:0" if (torch.cuda.is_available()) else "cpu")
    print("Device: %s" % device)

    gt = depth_trainer.DepthTrainer(constants.DEPTH_VERSION, constants.ITERATION, device, opts.g_lr, opts.d_lr)
    gt.update_penalties(opts.adv_weight, opts.likeness_weight)
    start_epoch = 0
    iteration = 0

    if (opts.load_previous):
        checkpoint = torch.load(constants.DEPTH_ESTIMATOR_CHECKPATH)
        start_epoch = checkpoint['epoch'] + 1
        iteration = checkpoint['iteration'] + 1
        gt.load_saved_state(iteration, checkpoint, constants.GENERATOR_KEY, constants.DISCRIMINATOR_KEY,
                            constants.OPTIMIZER_KEY)

        print("Loaded checkpt: %s Current epoch: %d" % (constants.DEPTH_ESTIMATOR_CHECKPATH, start_epoch))
        print("===================================================")

    # Create the dataloader
    train_loader = dataset_loader.load_transmission_dataset(constants.DATASET_HAZY_PATH_COMPLETE, constants.DATASET_DEPTH_PATH_COMPLETE, constants.batch_size, opts.img_to_load)
    test_loader = dataset_loader.load_transmision_test_dataset(constants.DATASET_VEMON_PATH_COMPLETE, constants.DATASET_DEPTH_PATH_COMPLETE, constants.display_size, 500)
    index = 0

    # Plot some training images
    if (constants.is_coare == 0):
        _, a, b = next(iter(train_loader))
        _, c, d = next(iter(test_loader))
        show_images(a, "Training - RGB Images")
        show_images(b, "Training - Depth Images")
        show_images(c, "Test - RGB Images")
        show_images(d, "Test - Depth Images")

    print("Starting Training Loop...")
    if (constants.is_coare == 0):
        for epoch in range(start_epoch, constants.num_epochs):
            # For each batch in the dataloader
            for i, train_data in enumerate(train_loader, 0):
                _, rgb_batch, depth_batch = train_data
                rgb_tensor = rgb_batch.to(device).float()
                depth_tensor = depth_batch.to(device).float()

                gt.train(rgb_tensor, depth_tensor)
                if (i % 500 == 0 and constants.is_coare == 0):
                    view_batch, view_rgb_batch, view_depth_batch = next(iter(test_loader))
                    view_rgb_batch = view_rgb_batch.to(device).float()
                    view_depth_batch = view_depth_batch.to(device).float()
                    gt.visdom_report(iteration, rgb_tensor, depth_tensor, view_rgb_batch, view_depth_batch)
                    iteration = iteration + 1
                    index = (index + 1) % len(test_loader)
                    if (index == 0):
                        test_loader = dataset_loader.load_transmision_test_dataset(constants.DATASET_VEMON_PATH_COMPLETE, constants.DATASET_DEPTH_PATH_COMPLETE, constants.display_size, 500)

                    gt.save_states(epoch, iteration, constants.DEPTH_ESTIMATOR_CHECKPATH, constants.GENERATOR_KEY, constants.DISCRIMINATOR_KEY, constants.OPTIMIZER_KEY)
    else:
        for i, train_data in enumerate(train_loader, 0):
            _, rgb_batch, depth_batch = train_data
            rgb_tensor = rgb_batch.to(device)
            depth_tensor = depth_batch.to(device)
            gt.train(rgb_tensor, depth_tensor)
            if (i % 100 == 0):
                print("Iterating %d " % i)

        # save every X epoch
        gt.save_states(start_epoch, iteration, constants.DEPTH_ESTIMATOR_CHECKPATH, constants.GENERATOR_KEY, constants.DISCRIMINATOR_KEY, constants.OPTIMIZER_KEY)


# FIX for broken pipe num_workers issue.
if __name__ == "__main__":
    main(sys.argv)
