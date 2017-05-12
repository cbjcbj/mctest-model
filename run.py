# encoding: utf-8
import os
import logging
import numpy as np

from keras.callbacks import EarlyStopping
from setup_logger import setup_logging

from model import PHM
from callbacks import LearningRateCutting, Evaluation
from keras.callbacks import ModelCheckpoint
import cPickle as pickle
import time

logger = logging.getLogger(__name__)


class McDataset(object):
    def __init__(self, data_path, which_dataset):
        self.data_path = data_path
        self.dataset_name = which_dataset
        self._load()

    def _load(self):
        import h5py
        print 'init dataset with h5 file.'
        meta_data = {}
        print 'data_path:', self.data_path
        f = h5py.File(self.data_path, 'r')
        dataset = f[self.dataset_name]
        print f.keys()
        print dataset.keys()
        print dataset['data'].keys()
        for key in dataset.attrs:
            meta_data[key] = dataset.attrs[key]

        # words_flatten = f['words_flatten'][0]
        # id2word = words_flatten.split('\n')
        id2word =  f['vocab'][:]
        # assert len(self.id2word) == f.attrs['vocab_len'], "%s != %s" % (len(id2word), f.attrs['vocab_len'])
        word2id = dict(zip(id2word, range(len(id2word))))
        meta_data['id2word'] = id2word
        meta_data['word2id'] = word2id
        meta_data['idfs'] = dataset['idfs'][:]

        meta_data['answer_size'] = dataset['data/train/input_answer'].shape[1]
        meta_data['n_s'] = dataset['data/train/input_story'].shape[1]
        meta_data['n_voc'] = len(id2word)
        meta_data['n_w_a'] = dataset['data/train/input_answer'].shape[-1]
        meta_data['n_w_q'] = dataset['data/train/input_question'].shape[-1]
        meta_data['n_w_qa'] = dataset['data/train/input_question_answer'].shape[-1]
        meta_data['n_w_s'] = dataset['data/train/input_story'].shape[-1]
        # meta_data['w2v_path'] = '/opt/dnn/word_embedding/glove.840B.300d.pandas.hdf5'
        # meta_data['stop_words_file'] = '/home/xihlin/workspace/ExamComprehension/examcomprehension/datasets/stopwords.txt'

        data = {}
        for key in dataset['data']:
            data[key] = {}
            for inner_key in dataset['data'][key]:
                data[key][inner_key] = dataset['data'][key][inner_key][:]
                shape_key = inner_key+"_shape"
                if not shape_key in meta_data:
                    meta_data[shape_key] = data[key][inner_key].shape
                    print(inner_key+"_shape:", meta_data[inner_key+"_shape"])
                if inner_key == 'input_story_attentive':
                    meta_data['max_len_input_story_attentive'] = data[key][inner_key].shape[1]

        print meta_data.keys()
        self.meta_data = meta_data
        self.data = data
        f.close()
        logger.info('finish init dataset with %s' % self.data_path)


def train_option(data_path, which_dataset, update_dict=None, EPOCHS=50):
    BATCH_SIZE = 64
    patience = 10
    dataset = McDataset(data_path, which_dataset)
    data = dataset.data
    train_data, valid_data, test_data = data['train'], data['valid'], data['test']

    lr_cutting = LearningRateCutting(patience=1, cut_ratio=0.8)  # 0.5
    eval_callback = Evaluation((test_data, test_data['y_hat']), monitor='acc')
    checkpoint = ModelCheckpoint('race_middle.model', monitor='val_acc', save_best_only=True)
    callbacks_list = [
                      EarlyStopping(patience=patience, verbose=1, monitor='val_acc'),
                      lr_cutting,
                      eval_callback,
                      # checkpoint,
                      ]

    model = PHM('model.yaml', dataset.meta_data, None, update_dict=update_dict)
    graph = model.build()
    # from ipdb import set_trace; set_trace()
    for i, node in enumerate(graph.get_layer('membedding_1').inbound_nodes):
        print i, node.inbound_layers[0].name
    print ''
    for i, node in enumerate(graph.get_layer('membedding_2').inbound_nodes):
        print i, node.inbound_layers[0].name
    graph.summary()

    try:
        logger.info('finished loading models')
        graph.fit(x=train_data, y=train_data['y_hat'],
                  validation_data=[valid_data, valid_data['y_hat']], batch_size=BATCH_SIZE, nb_epoch=EPOCHS, verbose=1,
                  shuffle=True, callbacks=callbacks_list
                  )
        with open('race_middle.model.pickle', 'w') as f:
            pickle.dump(graph, f)
    except KeyboardInterrupt:
        logger.info('interrupted by the user, and continue to eval on test.')
        time.sleep(2)
        with open('race_middle.model.pickle', 'w') as f:
            pickle.dump(graph, f)


if __name__ == '__main__':
    import argparse
    setup_logging(default_path='logging.yaml', default_level=logging.INFO)
    parser = argparse.ArgumentParser(description="train option model and print out results.")
    parser.add_argument("-p", "--datapath", type=str, help="path to hdf5 data")
    parser.add_argument("-d", "--dataset", type=str, default='middle', help="which dataset")
    parser.add_argument("-e", "--epoch", type=int, default=10, help="number of epoch to train.")
    args = parser.parse_args()

    train_option(args.datapath, args.dataset, EPOCHS=args.epoch)
    logger.info("**************Train_eval finished******************")
