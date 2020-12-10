import numpy as np
import matplotlib.pyplot as plt

import torch
from torch import nn
from torch.backends import cudnn
from torch.autograd import Variable
import torch.optim as optim
import torch.nn.functional as F
import torch.cuda
import torchvision.utils as v_utils
import torchvision.transforms as transforms
import torchvision.datasets as datasets
from torch.utils.data import Subset
from sklearn.model_selection import train_test_split

from models.stacked_model import StackedNetwork
from dataset import ExecutableDataset

from timeit import default_timer as timer

#====================PARAMETERS==========================
input_w = 128
input_h = 128
learning_rate = 0.0001
momentum = 0.9
N_epochs = 50
batch_size = 32

# Splits
train_split = 0.7
val_split = 0.2
test_split = 0.1

# Encoder Layer Parameters
hidden_enc_dim1 = 2000
hidden_enc_dim2 = 1000

# Perceptron Hidden Layer Parameters
hidden_mp_dim1 = 20
hidden_mp_dim2 = 20
hidden_mp_dim3 = 150
#========================================================

device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

# Train-val-test split function
def train_val_test_split(dataset, splits):
    datasets = {}

    # Two-way split
    if len(splits) == 2:
        first_idx, second_idx = train_test_split(list(range(dataset.__len__())), test_size=splits[1])
        datasets['first'] = Subset(dataset, first_idx)
        datasets['second'] = Subset(dataset, second_idx)

    # Three-way split
    elif len(splits) == 3:
        first_idx, second_third_idx = train_test_split(list(range(dataset.__len__())), test_size=1-splits[0])
        second_idx, third_idx = train_test_split(second_third_idx, test_size=splits[2]/(splits[1]+splits[2]))

        datasets['first'] = Subset(dataset, first_idx)
        datasets['second'] = Subset(dataset, second_idx)
        datasets['third'] = Subset(dataset, third_idx)

    return datasets

#============================================================================================================

# DATA TRANSFORMATION

transform_exec = transforms.Compose([
    transforms.Resize((input_h, input_w)),
    transforms.Grayscale(),
    transforms.ToTensor()
])

#============================================================================================================

# PATHS

plane_benign_path = '/Users/huymai/Datasets/executables/BenignPlane'
plane_corrupt_path = '/Users/huymai/Datasets/executables/CorruptPlane'

#============================================================================================================

# SPLIT Data

plane_benign_files =  ExecutableDataset(transform_exec, plane_benign_path, all='Benign')
plane_benign_split = train_val_test_split(plane_benign_files, splits=[train_split, val_split, test_split])

plane_benign_train_set = plane_benign_split['first']
plane_benign_val_set = plane_benign_split['second']
plane_benign_test_set = plane_benign_split['third']

plane_corrupt_files =  ExecutableDataset(transform_exec, plane_corrupt_path, all='Malware')
plane_corrupt_split = train_val_test_split(plane_corrupt_files, splits=[train_split, val_split, test_split])

plane_corrupt_train_set = plane_corrupt_split['first']
plane_corrupt_val_set = plane_corrupt_split['second']
plane_corrupt_test_set = plane_corrupt_split['third']

#============================================================================================================

# PUT SETS INTO DATALOADERS
plane_train_dataset = plane_corrupt_train_set + plane_benign_train_set
plane_val_dataset = plane_corrupt_val_set + plane_benign_val_set
plane_test_dataset = plane_corrupt_test_set + plane_benign_test_set

train_loader = torch.utils.data.DataLoader(plane_train_dataset, batch_size, shuffle=True)
val_loader = torch.utils.data.DataLoader(plane_val_dataset, batch_size, shuffle=True)
test_loader = torch.utils.data.DataLoader(plane_test_dataset, shuffle=False)

#============================================================================================================

# MODEL
print('=======TRANSFER LEARNING ON PLANE=======')

# Instantiation
transfer_plane_model = StackedNetwork(
    input_size=input_w*input_h,
    encode_layers=[hidden_enc_dim1, hidden_enc_dim2],
    mp_layers=[hidden_mp_dim1, hidden_mp_dim2, hidden_mp_dim3, 1],
    device=device
).to(device)

# Load pretrained model
pretrained_stacked_path = './saved_models/pretrained_stacked.pt'
transfer_plane_model.load_state_dict(torch.load(pretrained_stacked_path))

# Fine-tune model and freeze encoder
train_st_percentages, val_st_percentages, train_losses, val_losses \
    =  transfer_plane_model.train_and_val(train_loader, val_loader, epochs=N_epochs, batch_size=batch_size, lr=learning_rate, momentum=momentum, freeze=1)

# Test model on test set
transfer_plane_model.test(test_loader)

# Save transfer plane model
transfer_plane_model_path = './saved_models/pretrained_plane.pt'
transfer_plane_model.save_model(transfer_plane_model_path)
#============================================================================================================

# RESULTS
accuracies_path = './results/stackedaccuraciesplane.png'
losses_path = './results/stackedlossesplane.png'

# Stacked Accuracies over N epochs
plt.figure(1)
plt.title('Stacked Network Accuracies (Plane)')
plt.plot([i + 1 for i in range(len(train_st_percentages))], train_st_percentages, 'b-', label='Training')
plt.plot([i + 1 for i in range(len(val_st_percentages))], val_st_percentages, 'r-', label='Validation')
plt.legend(loc='lower right')
plt.xlabel('Epochs')
plt.ylabel('Accuracy (%)')
plt.axis([1, N_epochs, 0, 100])
plt.savefig(accuracies_path)

# Stacked Losses over N epochs
plt.figure(2)
plt.title('Stacked Network Losses (Plane)')
plt.plot([i + 1 for i in range(len(train_losses))], train_losses, 'b-', label='Training')
plt.plot([i + 1 for i in range(len(val_losses))], val_losses, 'r-', label='Validation')
plt.legend(loc='upper right')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.savefig(losses_path)
