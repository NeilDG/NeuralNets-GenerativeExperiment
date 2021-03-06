# -*- coding: utf-8 -*-
"""
Multistyle trainer
Created on Wed Nov  6 19:41:58 2019

@author: delgallegon
"""

import os
from model import style_transfer_gan
from loaders import dataset_loader
import constants
from model import multistyle_net
from model import style_transfer_gan
import torch
from torch import optim
import numpy as np
from torch.utils.tensorboard import SummaryWriter
import matplotlib.pyplot as plt
import torch.nn as nn
import torchvision.utils as vutils
from torch import autograd
from utils import logger
from utils import tensor_utils
import torchvision.models as models

print = logger.log


class MultiStyleTrainer:
    def __init__(self, version, iteration, gpu_device, writer, lr = 0.0002, weight_decay = 0.0, betas = (0.5, 0.999)):
        self.gpu_device = gpu_device
        self.lr = lr
        self.version = version
        self.iteration = iteration
        self.writer = writer
        self.visualized = False
        
        self.vgg16 = models.vgg16(True)
        for param in self.vgg16.parameters():
            param.requires_grad = True
        
        #return output of last layer just before softmax
        self.vgg16 = nn.Sequential(*list(self.vgg16.features.children())[:43])
        self.vgg16.to(self.gpu_device)
        
        self.style_model = multistyle_net.Net()
        self.style_model.to(self.gpu_device)
        
        self.discriminator = style_transfer_gan.Discriminator() #create discriminator for adversarial loss
        self.discriminator.to(self.gpu_device)
        
        self.optimizer = optim.Adam(self.style_model.parameters(), lr = lr, betas=betas, weight_decay=weight_decay)
        self.optimizerD = optim.Adam(self.discriminator.parameters(), lr=lr, betas=betas, weight_decay=weight_decay)
        
        self.mse_loss = nn.MSELoss()
        self.bce_loss = nn.BCELoss()
        
        self.style_losses = []
        self.content_losses = []
        self.D_losses = []
        
        self.content_weight = 100.0; self.style_weight = 500.0; self.adv_weight = 0.0
    
    def update_weight(self, content_weight, style_weight):
        self.content_weight = content_weight
        self.style_weight = style_weight
        print("Weights updated to %f and %f" %(self.content_weight, self.style_weight))
        
    # Input = image
    # Performs a discriminator forward-backward pass, then a generator forward-backward pass
    # a = vemon image
    # b = gta image
    def train(self, vemon_tensor, gta_tensor, iteration):
        
        vgg_getter = [tensor_utils.SaveFeatures(self.vgg16[i]) for i in [3, 8, 15, 22]];
        
        self.optimizer.zero_grad()
        self.style_model.train()
        gta_tensor = tensor_utils.preprocess_batch(gta_tensor)
        vemon_tensor = tensor_utils.preprocess_batch(vemon_tensor)
        #gta_tensor = tensor_utils.subtract_imagenet_mean_batch(gta_tensor)
        self.vgg16(gta_tensor)
        features_gta = [sf.features.clone() for sf in vgg_getter]
        
        gram_gta = [tensor_utils.gram_matrix(y) for y in features_gta]
        
        vemon_transfer = self.style_model(vemon_tensor, gta_tensor)
        vemon_tensor_copy = autograd.Variable(vemon_tensor.data.clone())
        
        #vemon_transfer = tensor_utils.subtract_imagenet_mean_batch(vemon_transfer)
        #vemon_tensor_copy = tensor_utils.subtract_imagenet_mean_batch(vemon_tensor_copy)
        
        self.vgg16(vemon_transfer)
        vemon_transfer_features = [sf.features.clone() for sf in vgg_getter]
        
        self.vgg16(vemon_tensor_copy)
        vemon_orig_features = [sf.features.clone() for sf in vgg_getter]
        
        single_feature = autograd.Variable(vemon_orig_features[1].data, requires_grad=False)
        
        #content loss of conv1 features
        content_loss = self.content_weight * self.mse_loss(vemon_transfer_features[1], single_feature)
        
        style_loss = 0.0
        n_batch = len(vemon_tensor)
        for m in range(len(vemon_transfer_features)):
            vemon_transfer_gram = tensor_utils.gram_matrix(vemon_transfer_features[m])
            gram_s = autograd.Variable(gram_gta[m].data, requires_grad=False).repeat(n_batch, 1, 1)
            style_loss += self.style_weight * self.mse_loss(vemon_transfer_gram, gram_s[:n_batch, :, :])
        
        #get adversarial loss
        # prediction = self.discriminator(vemon_transfer)
        # real_tensor = torch.ones_like(prediction)
        # fake_tensor = torch.zeros_like(prediction)
        
        #adv_loss = self.bce_loss(prediction, real_tensor) * self.adv_weight
        
        total_loss = content_loss + style_loss
        total_loss.backward()
        self.optimizer.step()
        
        #optimize discriminator
        # self.discriminator.train()
        # self.optimizerD.zero_grad()
        # D_A_real_loss = self.bce_loss(self.discriminator(gta_tensor), real_tensor)
        # D_A_fake_loss = self.bce_loss(self.discriminator(vemon_transfer.detach()), fake_tensor)
        # errD = D_A_real_loss + D_A_fake_loss
        # errD.backward()
        # self.optimizerD.step()
        
        # Save Losses for plotting later
        self.style_losses.append(style_loss.item())
        self.content_losses.append(content_loss.item())
        #self.D_losses.append(adv_loss.item())
        
        #print("Output size: %s", fake_A.size())
        if(iteration % 500 == 0):
            print("Iteration: %d Content loss: %f Style loss: %f" % (iteration, content_loss.item(), style_loss.item()))
            #print("Iteration: %d Content loss: %f Style loss: %f Adv loss: %f" % (iteration, content_loss.item(), style_loss.item(), adv_loss.item()))

    def verify(self, vemon_tensor, gta_tensor):        
        gta_tensor = tensor_utils.preprocess_batch(gta_tensor)
        vemon_tensor = tensor_utils.preprocess_batch(vemon_tensor)
        #gta_tensor = tensor_utils.subtract_imagenet_mean_batch(gta_tensor)
        
        with torch.no_grad():
            fake_ab = self.style_model(vemon_tensor, gta_tensor).detach() 
        
        #gta_tensor = tensor_utils.add_imagenet_mean_batch(gta_tensor)
        gta_tensor = tensor_utils.make_rgb(gta_tensor)
        vemon_tensor = tensor_utils.make_rgb(vemon_tensor)
        fake_ab = tensor_utils.make_rgb(fake_ab)
        
        fig, ax = plt.subplots(3, 1)
        fig.set_size_inches(40, 10)
        
        ims = np.transpose(vutils.make_grid(vemon_tensor, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[0].set_axis_off()
        ax[0].imshow(ims)
        
        ims = np.transpose(vutils.make_grid(fake_ab, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[1].set_axis_off()
        ax[1].imshow(ims)
        
        ims = np.transpose(vutils.make_grid(gta_tensor, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[2].set_axis_off()
        ax[2].imshow(ims)
        
        plt.subplots_adjust(left = 0.06, wspace=0.0, hspace=0.15) 
        plt.show()
        
        #verify reconstruction loss with MSE. for reporting purposes
        mse_loss = nn.MSELoss()
        self.current_mse_loss = mse_loss(fake_ab, gta_tensor)
    
    def verify_and_save(self, vemon_tensor, gta_tensor, file_number):
        LOCATION = os.getcwd() + "/figures/"
        with torch.no_grad():
            fake = self.G_A(vemon_tensor).detach().cpu()
        
        fig, ax = plt.subplots(3, 1)
        fig.set_size_inches(15, 15)
        fig.tight_layout()
        
        ims = np.transpose(vutils.make_grid(vemon_tensor, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[0].set_axis_off()
        ax[0].imshow(ims)
        
        ims = np.transpose(vutils.make_grid(fake, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[1].set_axis_off()
        ax[1].imshow(ims)
        
        ims = np.transpose(vutils.make_grid(gta_tensor, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[2].set_axis_off()
        ax[2].imshow(ims)
        
        plt.subplots_adjust(left = 0.06, wspace=0.0, hspace=0.15) 
        plt.savefig(LOCATION + "result_" + str(file_number) + ".png")
        plt.show()
    
    def vemon_verify(self, vemon_tensor, gta_tensor, file_number):
        LOCATION = os.getcwd() + "/figures/"
        
        gta_tensor = tensor_utils.preprocess_batch(gta_tensor)
        vemon_tensor = tensor_utils.preprocess_batch(vemon_tensor)
        gta_tensor = tensor_utils.subtract_imagenet_mean_batch(gta_tensor)
        
        with torch.no_grad():
            fake = self.style_model(vemon_tensor, gta_tensor).detach()
        
        gta_tensor = tensor_utils.make_rgb(gta_tensor)
        vemon_tensor = tensor_utils.make_rgb(vemon_tensor)
        fake = tensor_utils.make_rgb(fake)
        
        #resize tensors for better viewing
        resized_normal = nn.functional.interpolate(vemon_tensor, scale_factor = 2.0, mode = "bilinear", recompute_scale_factor = True)
        resized_fake = nn.functional.interpolate(fake, scale_factor = 2.0, mode = "bilinear", recompute_scale_factor = True)
        
        print("New shapes: %s %s" % (np.shape(vemon_tensor), np.shape(resized_normal)))
        
        fig, ax = plt.subplots(2, 1)
        fig.set_size_inches(34, 14)
        fig.tight_layout()
        
        ims = np.transpose(vutils.make_grid(resized_normal, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[0].set_axis_off()
        ax[0].imshow(ims)
        
        ims = np.transpose(vutils.make_grid(resized_fake, nrow = 16, padding=2, normalize=True).cpu(),(1,2,0))
        ax[1].set_axis_off()
        ax[1].imshow(ims)
        
        plt.subplots_adjust(left = 0.06, wspace=0.0, hspace=0.15) 
        plt.savefig(LOCATION + "result_" + str(file_number) + ".png")
        plt.show()
        
    #reports metrics to necessary tools such as tensorboard
    def report(self, epoch):
        self.log_weights("style_A", self.style_model, self.writer, epoch)
        self.tensorboard_plot(epoch)

    def log_weights(self, model_name, model, writer, epoch):
        #log update in weights
        for module_name,module in model.named_modules():
            for name, param in module.named_parameters():
                if(module_name != ""):
                    #print("Layer added to tensorboard: ", module_name + '/weights/' +name)
                    writer.add_histogram(model_name + "/" + module_name + '/' +name, param.data, global_step = epoch)
    
    def tensorboard_plot(self, epoch):
        ave_style_loss = sum(self.style_losses) / (len(self.style_losses) * 1.0)
        ave_content_loss = sum(self.content_losses) / (len(self.content_losses) * 1.0)
        #ave_adv_loss = sum(self.D_losses) / (len(self.D_losses) * 1.0)
        
        self.writer.add_scalars(self.version +'/loss' + "/" + self.iteration, {'style_loss' :ave_style_loss, 'content_loss' : ave_content_loss,
                                                                               'mse_loss' :self.current_mse_loss},
                           global_step = epoch + 1)
        self.writer.close()
        
        print("Epoch: %d Content loss: %f Style loss: %f" % (epoch, ave_content_loss, ave_style_loss))
    
    def load_saved_state(self, checkpoint, model_key, optimizer_key):
        self.style_model.load_state_dict(checkpoint[model_key])
        self.optimizer.load_state_dict(checkpoint[model_key + optimizer_key])
        
        self.discriminator.load_state_dict(checkpoint[model_key + constants.DISCRIMINATOR_KEY])
        self.optimizerD.load_state_dict(checkpoint[model_key + constants.DISCRIMINATOR_KEY + optimizer_key])
    
    def save_states(self, epoch, path, model_key, optimizer_key):
        save_dict = {'epoch': epoch}
        netGA_state_dict = self.style_model.state_dict()
        optimizerG_state_dict = self.optimizer.state_dict()
        
        netD_state_dict = self.discriminator.state_dict()
        optimizerD_state_dict = self.optimizerD.state_dict()
        
        save_dict[model_key] = netGA_state_dict
        save_dict[model_key + optimizer_key] = optimizerG_state_dict
        
        save_dict[model_key + constants.DISCRIMINATOR_KEY] = netD_state_dict
        save_dict[model_key + constants.DISCRIMINATOR_KEY + optimizer_key] = optimizerD_state_dict
    
        torch.save(save_dict, path)
        print("Saved model state: %s Epoch: %d" % (len(save_dict), (epoch + 1)))