import numpy as np
import pandas as pd
import os
import tensorflow as tf
from sklearn.model_selection import train_test_split
import argparse
import json
import subprocess
from tensorflow.keras.utils import to_categorical

from tensorflow.keras.layers import Dense, Dropout, Flatten, Conv2D, MaxPool2D
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.optimizers import RMSprop
import boto3
from PIL import Image
from numpy import array

from PIL import Image
from PIL import Image, ImageChops, ImageEnhance

np.random.seed(2)


def convert_to_ela_image(path, quality):
    filename = path
    resaved_filename = 'tempresaved.jpg'
    im = Image.open(filename)
    bm = im.convert('RGB')
    im.close()
    im=bm
    im.save(resaved_filename, 'JPEG', quality = quality)
    resaved_im = Image.open(resaved_filename)
    ela_im = ImageChops.difference(im, resaved_im)
    extrema = ela_im.getextrema()
    max_diff = max([ex[1] for ex in extrema])
    if max_diff == 0:
        max_diff = 1
    scale = 255.0 / max_diff
    ela_im = ImageEnhance.Brightness(ela_im).enhance(scale)
    im.close()
    bm.close()
    resaved_im.close()
    del filename
    del resaved_filename
    del im
    del bm
    del resaved_im
    del extrema
    del max_diff
    del scale
    return ela_im

def build_image_list(path_to_image, label, images):
    for file in os.listdir(path_to_image):
        try:
            if file.endswith('jpg') or file.endswith('JPG') or file.endswith('jpeg') or file.endswith('JPEG'):
                if int(os.stat(path_to_image + file).st_size) > 10000:
                    line = path_to_image + file  + ',' + label + '\n'
                    images.append(line)
        except:
            print(path_to_image + file)
    return images


def _parse_args():
    parser = argparse.ArgumentParser()

    # Data, model, and output directories
    # model_dir is always passed in from SageMaker. By default this is a S3 path under the default bucket.
    parser.add_argument('--model_dir', type=str)
    parser.add_argument('--sm-model-dir', type=str, default=os.environ.get('SM_MODEL_DIR'))
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN'))
    parser.add_argument('--hosts', type=list, default=json.loads(os.environ.get('SM_HOSTS')))
    parser.add_argument('--current-host', type=str, default=os.environ.get('SM_CURRENT_HOST'))

    return parser.parse_known_args()


if __name__ == "__main__":
    args, unknown = _parse_args()
    
    s3 = boto3.client("s3")

    print("ARGS", args)
    #print(subprocess.run([f"aws s3 cp --recursive {args.train} ./"],
    #               shell=True))
    
    custom_path_original = f'{args.train}/training/original/'
    custom_path_tampered = f'{args.train}/training/forged/'
    training_data_set = 'dataset.csv'
    
    images = []
    images = build_image_list(custom_path_original, '0', images)
    images = build_image_list(custom_path_tampered, '1', images)
    
    image_name = []
    label = []
    for i in range(len(images)):
        image_name.append(images[i][0:-3])
        label.append(images[i][-2])
    
    dataset = pd.DataFrame({'image':image_name,'class_label':label})
    dataset.to_csv(training_data_set,index=False)
    
    dataset = pd.read_csv('dataset.csv')
    X = []
    Y = []
    for index, row in dataset.iterrows():
        X.append(array(convert_to_ela_image(row[0], 90).resize((128, 128))).flatten() / 255.0)
        Y.append(row[1])
    X = np.array(X)
    Y = to_categorical(Y, 2)
    
    
    X = X.reshape(-1, 128, 128, 3)
    
    X_train, X_val, Y_train, Y_val = train_test_split(X, Y, test_size = 0.2, random_state=5)
    
    
    model = tf.keras.models.Sequential()
    
    model.add(Conv2D(filters = 32, kernel_size = (3,3),padding = 'valid', 
                     activation ='relu', input_shape = (128,128,3)))
    model.add(Conv2D(filters = 32, kernel_size = (3,3),padding = 'valid', 
                     activation ='relu'))
    model.add(MaxPool2D(pool_size=(2,2)))
    model.add(Dropout(0.25))
    model.add(Flatten())
    model.add(Dense(256, activation = "relu"))
    model.add(Dropout(0.5))
    model.add(Dense(2, activation = "softmax"))
    
    
    optimizer = RMSprop(learning_rate=0.0005, rho=0.9, epsilon=1e-08, decay=0.0)
    model.compile(optimizer = optimizer , loss = "categorical_crossentropy", metrics=["accuracy"])
    
    epochs = 30
    batch_size = 100
    
    early_stopping = EarlyStopping(monitor='val_accuracy',
                                  min_delta=0,
                                  patience=2,
                                  verbose=0, mode='auto')
    
    history = model.fit(X_train, Y_train, batch_size = batch_size, epochs = epochs, 
              validation_data = (X_val, Y_val), verbose = 2)#, callbacks=[early_stopping])
    
    
    model.save(os.path.join(args.sm_model_dir, '000000001'))