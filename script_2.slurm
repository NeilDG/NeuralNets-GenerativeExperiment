#!/bin/bash
#SBATCH -J DN_5
#SBATCH --partition=gpu
#SBATCH --qos=12c-1h_2gpu
#SBATCH --cpus-per-task=4
#SBATCH -G 1 
#SBATCH --ntasks=1
#SBATCH --output=dn_job_1.out
#SBATCH --mail-user=neil.delgallego@dlsu.edu.ph 
#SBATCH --mail-type=END 

# check which GPU device was allocated
echo "CUDA_DEVICE=/dev/nvidia/$CUDA_VISIBLE_DEVICES"
nvidia-smi

# prepare working environment
module load anaconda
module load cuda/10.1_cudnn-7.6.5

source activate NeilGAN
srun python div2k_main.py --iteration=5 --coare=1 --cycle_weight=500.0 --img_to_load=71200 --load_previous=0
source deactivate

for i in {1..500}
    do
        source activate NeilGAN
        srun python div2k_main.py --iteration=5 --coare=1 --cycle_weight=500.0 --img_to_load=71200 --load_previous=1
        source deactivate
    done