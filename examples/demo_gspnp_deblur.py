import numpy as np
import deepinv as dinv
import hdf5storage
import torch
import os
from torch.utils.data import DataLoader
from deepinv.models.denoiser import ProxDenoiser, ScoreDenoiser
from deepinv.optim.data_fidelity import *
from deepinv.optim.optimizers import *
from deepinv.training_utils import test
from torchvision import datasets, transforms
from deepinv.utils.parameters import get_GSPnP_params, initialize_stepsizes

torch.manual_seed(0)

num_workers = 4 if torch.cuda.is_available() else 0  # set to 0 if using small cpu, else 4

train = False

ckpt_path = '../checkpoints/GSDRUNet.ckpt'
denoiser_name = 'gsdrunet'
batch_size = 1
n_channels = 3
pretrain = True

problem = 'deblur'
G = 1
img_size = 256

dataset = 'starfish'
dataset_path = f'../../datasets/{dataset}'
save_dir = f'/beegfs/shurault/deepinv/datasets/{dataset}/{problem}/'

noise_level_img = 0.03

crit_conv = 'cost'
thres_conv = 1e-5
early_stop = True
verbose = True

k_index = 1

#TODO : add kernel downloading code
kernels = hdf5storage.loadmat('/beegfs/shurault/deepinv/kernels/Levin09.mat')['kernels']
filter_np = kernels[0,k_index].astype(np.float64)
filter_torch = torch.from_numpy(filter_np).unsqueeze(0).unsqueeze(0)

p = dinv.physics.BlurFFT(img_size = (3,img_size,img_size), filter=filter_torch, device=dinv.device, noise_model = dinv.physics.GaussianNoise(sigma=noise_level_img))
data_fidelity = L2()

val_transform = transforms.Compose([
            transforms.ToTensor(),
 ])

dataset = datasets.ImageFolder(root=dataset_path, transform=val_transform)
dinv.datasets.generate_dataset(train_dataset=dataset, test_dataset=None,
                               physics=p, device=dinv.device, save_dir=save_dir, max_datapoints=1,
                               num_workers=num_workers)
dataset = dinv.datasets.HDF5Dataset(path=f'{save_dir}/dinv_dataset0.h5', train=True)
dataloader = DataLoader(dataset, batch_size=batch_size, num_workers=num_workers, shuffle=False)

model_spec = {'name': denoiser_name,
              'args': {
                    'in_channels':n_channels+1, 
                    'out_channels':n_channels,
                    'pretrained': ckpt_path, 
                    'train': False, 
                    'device':dinv.device
                    }}

lamb, sigma_denoiser, stepsize, max_iter = get_GSPnP_params(problem, noise_level_img, k_index)
stepsize, sigma_denoiser = initialize_stepsizes(stepsize, sigma_denoiser, max_iter)
grad_g = ScoreDenoiser(model_spec)
F_fn = lambda x,y,physics,it : lamb*data_fidelity.f(physics.A(x), y) + grad_g.denoiser.potential(x,sigma_denoiser[it])
model = Optim(algo_name = 'PGD', grad_g=grad_g, g_first = True, data_fidelity=data_fidelity, lamb=lamb, stepsize=stepsize, device=dinv.device,
             g_param=sigma_denoiser, early_stop = early_stop, max_iter=max_iter, crit_conv=crit_conv, thres_conv=thres_conv, backtracking=False, 
             F_fn=F_fn, return_dual=True, verbose=True)

test(model=model,  # Safe because it has forward
    test_dataloader=dataloader,
    physics=p,
    device=dinv.device,
    plot=True,
    plot_input=True,
    save_folder='../results/',
    save_plot_path='../results/results_pnp.png',
    verbose=verbose)
