"""
@authors: faurand, chardes, ehagensieker
"""
import argparse
import sys
import tensorflow as tf
from model import BaselineModel, MultimodalModel
from loss import KLDivergence
from utils import create_summary_writers, save_hist
from train import train
from validate import validate
import matplotlib.pyplot as plt
import datetime


# Select various options for training the model. The default values are stated in each argument
parser = argparse.ArgumentParser()

parser.add_argument('--data', default='SALICON', type=str)
parser.add_argument('--colab', default=1, type=int)

parser.add_argument('--model', default="baseline", type=str)
parser.add_argument('--save', default=0, type=int)
parser.add_argument('--load_model', default=0, type=int)

parser.add_argument('--use_pretrained', default=1, type=int)
parser.add_argument('--fine_tune', default=0, type=int)

parser.add_argument('--lr', default=1e-4, type=float)
parser.add_argument('--lr_sched', default=0, type=int)
parser.add_argument('--optim', default="Adam", type=str)
parser.add_argument('--step_size', default=5, type=int)

parser.add_argument('--l1_norm', default=None, type=int)
parser.add_argument('--l2_norm', default=None, type=int)

parser.add_argument('--no_epochs', default=24, type=int)
parser.add_argument('--batch_size', default=32, type=int)

#run parser and place extracted data in args object
args = parser.parse_args()

def preprocessing(data,args):
    '''
    Preprocess the input data for training by removing the color channel of the saliency map and
    by shuffling, batching and prefetching.

    Arguments: 
        data:tf.data.Dataset
            The input data to be preprocessed, with left out image captions.
        args:argparse.Namespace
            The namespace object containing the parsed command-line arguments.
    Returns: 
        data:tf.data.Dataset
            The preprocessed input data. 
    '''
    data = data.map(lambda img,_,sal: (img, tf.squeeze(sal, axis=2)))
    data = data.shuffle(514).batch(args.batch_size).prefetch(buffer_size=tf.data.AUTOTUNE)
    return data

def preprocessing_multi(data,args):
    '''
    Preprocess the input data for training the multimodal model by removing the color channel of the saliency map, casting the captions
    into float values and by shuffling, batching and prefetching.

    Arguments: 
        data:tf.data.Dataset
            The input data to be preprocessed.
        args:argparse.Namespace
            The namespace object containing the parsed command-line arguments.
    Returns: 
        data:tf.data.Dataset
            The preprocessed input data. 
    '''
    data = data.map(lambda img,cap,sal: ((img, tf.cast(cap, dtype=tf.float32)), tf.squeeze(sal,axis = 2)))
    data = data.shuffle(514).batch(args.batch_size).prefetch(buffer_size=tf.data.AUTOTUNE)
    return data

# Set the parent directory depending on whether working on Google colab or not
if args.colab:
    parent_dir = '/content/drive/MyDrive/Project ANN'
else:
    parent_dir = '..'

if args.data == 'capgaze1':
    print("Data: capgaze1")
    dataset_path = f'{parent_dir}/data/tfds_capgaze1'
    
    ds = tf.data.Dataset.load(dataset_path, compression='GZIP')

else:
    print("Data: SALICON")
    dataset_path = f'{parent_dir}/data/tfds_salicon'
    
    train_ds = tf.data.Dataset.load(dataset_path + '/train2014', compression='GZIP')
    test_ds = tf.data.Dataset.load(dataset_path + '/val2014', compression='GZIP')   

#choose the optimizer you wanna test
if args.optim=="Adam":
    optimizer = tf.keras.optimizers.Adam(learning_rate=args.lr)
if args.optim=="Adagrad":
    optimizer = tf.keras.optimizers.Adagrad(learning_rate=args.lr)
if args.optim=="SGD":
    optimizer = tf.keras.optimizers.SGD(learning_rate=args.lr, momentum = 0.9)
if args.lr_sched:
    scheduler = tf.keras.optimizers.schedules.ExponentialDecay(initial_learning_rate=args.lr, decay_steps=args.step_size, decay_rate=0.1)
    optimizer = tf.keras.optimizers.Adam(learning_rate=scheduler)

# Set up directories to store the results
results_dir=f'{parent_dir}/results'
current_time = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
config_name = f'{args.model}_{args.data}_{current_time}'

# Choose the model to be used
if args.model == "baseline":
    print("Model: Baseline Model")
    model = BaselineModel(fine_tune=args.fine_tune, use_pretrained=args.use_pretrained,loss_function=KLDivergence(), optimizer=optimizer,l1_norm=args.l1_norm,l2_norm=args.l2_norm)
    if args.load_model:
        model.load_weights(f"{results_dir}/saved_model_baseline")
    if args.data == 'capgaze1':
        ds = preprocessing(ds,args)
    else:
        train_ds = preprocessing(train_ds,args)
        test_ds = preprocessing(test_ds,args)

elif args.model == "multimodal":
    print("Model: Multimodal Model")
    model = MultimodalModel(fine_tune=args.fine_tune, use_pretrained=args.use_pretrained, loss_function=KLDivergence(),optimizer=optimizer,l1_norm=args.l1_norm,l2_norm=args.l2_norm)
    if args.load_model:
        model.load_weights(f"{results_dir}/saved_model_multimodal")
    if args.data == 'capgaze1':
        ds = preprocessing_multi(ds,args)
    else:
        train_ds = preprocessing_multi(train_ds,args)
        test_ds = preprocessing_multi(test_ds,args)

#to visualize the losses later
hist = {"train_loss":[],
        "train_AUC":[],
        "train_CC":[],
        "train_NSS":[],
        "train_KLDiv":[],
        "train_SIM":[],
        "test_loss":[],
        "test_AUC":[],
        "test_CC":[],
        "test_NSS":[],
        "test_KLDiv":[],
        "test_SIM":[]}
hist_val = {"test_loss":[],
            "test_AUC":[],
            "test_CC":[],
            "test_NSS":[],
            "test_KLDiv":[],
            "test_SIM":[]}

# Train/test the model        
for epoch in range(0, args.no_epochs):        
    train_summary_writer, val_summary_writer = create_summary_writers(args, config_name, results_dir)
    if args.data == 'capgaze1':
        hist = validate(model, ds, epoch, args, val_summary_writer, hist_val, config_name, results_dir)
    else:
        hist = train(model, train_ds, test_ds, epoch, args, train_summary_writer, val_summary_writer, hist, config_name, results_dir)
    
save_hist(hist, config_name, results_dir)