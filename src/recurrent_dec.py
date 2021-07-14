"""
recurrent_dec.py offers methods to compute beam search and greedy search 
translations are made using the RNN model from recurrent_nn.py
"""
import os
import math
import time
import multiprocessing
import itertools
from numpy.testing._private.utils import tempdir
import tensorflow as tf
import numpy as np
import random

from tensorflow.keras import metrics
import batches
import metrics
from encoder import revert_bpe
import utility as ut
import recurrent_nn as rnn
from dictionary import dic_tar, dic_src
from utility import cur_dir, read_from_file
import tensorflow_addons as tfa
from tensorflow.keras.backend import argmax
from tensorflow.keras.backend import get_value

# TODO create pool to translate the hole dev file

# +2 for start and end of sequence symbol
max_line = 0
try:
    max_line = (
        batches.get_max_line(
            os.path.join(cur_dir, "train_data", "multi30k_subword.de"),
            os.path.join(cur_dir, "train_data", "multi30k_subword.en"),
        )
        + 2
    )
except Exception as exx:
    print("Issue with max_line {}".format(exx))


def save_translation(fd, bleu_score):
    """saves the list of strings in fd with prefix bleu_score"""
    ut.save_list_as_txt(
        os.path.join(
            cur_dir,
            "de_en_translation",
            "beam_bleu=" + str(bleu_score) + "_prediction.de",
        ),
        fd,
        strings=True,
    )

    # revert bpe on file
    revert_bpe(
        os.path.join(
            cur_dir,
            "de_en_translation",
            "beam_bleu=" + str(bleu_score) + "_prediction.de",
        ),
    )


# use this to save all the k predictions
def save_k_txt(file_txt, k):
    """provided an integer k and encoded text saves beam predictions into file system"""
    keys_list = dic_tar.get_keys()
    txt_list = [[] for _ in range(k)]
    for elem in file_txt:
        sentence = [[] for _ in range(k)]
        for i in range(k):
            str_lines = map(lambda x: keys_list[x], elem[i][0])
            sentence = list(str_lines)
            txt_list[i].append(sentence)
    for i in range(k):
        ut.save_list_as_txt(
            os.path.join(
                cur_dir,
                "de_en_translation",
                "beam_k=" + str(k) + "_prediction" + str(i) + ".de",
            ),
            txt_list[i],
        )
        revert_bpe(
            os.path.join(
                cur_dir,
                "de_en_translation",
                "beam_k=" + str(k) + "_prediction" + str(i) + ".de",
            )
        )


def roll_out_encoder(sentence, search=True, batch_size=1):
    """builds and returns a model from model's path"""
    enc, dec = get_enc_dec_paths()
    test_model = rnn.Translator(len(dic_tar), len(dic_src), 200, 200, batch_size)
    dec_input = [[dic_src.bi_dict["<s>"]] + [0 for _ in range(max_line - 1)]]
    dec_input = np.array(dec_input)
    temp_enc = tf.zeros((batch_size, dec_input.shape[1]), dtype=tf.float32)
    temp_dec = tf.zeros((batch_size, dec_input.shape[1]), dtype=tf.float32)

    enc_output, h, c = test_model.encoder(temp_enc, None)

    dec_output, _ = test_model.decoder((temp_dec, enc_output), None)

    test_model.encoder.load_weights(enc)
    test_model.decoder.load_weights(dec)
    if search:
        sentence = np.array([sentence])
        enc_output, h, c = test_model.encoder(sentence, None)
        dec_output, _ = test_model.decoder((dec_input, enc_output), [h, c])

    return test_model, enc_output, dec_output, h, c


def load_encoder(inputs, batch_size):

    enc, dec = get_enc_dec_paths()
    test_model = rnn.Encoder(len(dic_src), 200, 200, batch_size)
    temp = tf.zeros((batch_size, max_line), dtype=tf.float32)
    test_model(temp, None)

    test_model.load_weights(enc)
    outputs, h, c = test_model(inputs, None)
    return outputs, h, c


def load_decouder(batch_size):
    enc, dec = get_enc_dec_paths()
    test_model = rnn.Decoder(len(dic_tar), 200, 200, batch_size)
    temp = tf.zeros((batch_size, max_line), dtype=tf.float32)
    enc_temp = tf.zeros((batch_size, max_line, 200), dtype=tf.float32)

    test_model((temp, enc_temp))
    test_model.load_weights(dec)
    return test_model


def translator(sentence, k=1):
    batch_size = len(sentence)
    enc_outputs, enc_h, enc_c = load_encoder(sentence, 200)
    decoder = load_decouder(1)
    result = []
    for enc_output, h, c in zip(enc_outputs, enc_h, enc_c):
        dec_input = [[dic_src.bi_dict["<s>"]] + [0 for _ in range(max_line - 1)]]
        dec_input = np.array(dec_input)
        dec_output, _ = decoder((dec_input, enc_output), [[h], [c]])
        first_pred = tf.math.top_k(dec_output, k)
        candidate_sentences = []
        for i in range(k):
            candidate_sentences.append(
                [
                    [dic_tar.bi_dict["<s>"], get_value(first_pred.indices[0][0][i])],
                    -math.log(get_value(first_pred.values[0][0][i])),
                ]
            )
        pred_values = []
        for index in range(1, max_line):
            all_candidates = []
            for j, _ in enumerate(candidate_sentences):
                pre_pred_word = candidate_sentences[j][0]
                if pre_pred_word[-1] == dic_tar.bi_dict["</s>"]:
                    all_candidates.append(candidate_sentences[j])
                    continue

                pre_sentence = tf.keras.preprocessing.sequence.pad_sequences(
                    [pre_pred_word], maxlen=max_line, value=0, padding="post"
                )
                pred_word, _ = decoder((pre_sentence, enc_output), [[h], [c]])

                k_best = tf.math.top_k(pred_word, k=k)

                seq, score = candidate_sentences[j]
                for x, _ in enumerate(k_best.indices):
                    candidate = [
                        seq + [get_value(k_best.indices[0][index][x])],
                        score - math.log(get_value(k_best.values[0][index][x])),
                    ]
                    all_candidates.append(candidate)
            ordered = sorted(all_candidates, key=lambda tup: tup[1])
            candidate_sentences = ordered[:k]
        result.append(candidate_sentences)
    return result


def fast_beam_search(source, k, batch_size):
    result = []
    start = 0
    ende = batch_size
    src_len = len(source)
    set_off = time.time()
    while src_len > ende:
        print(start)
        result = result + translator(source[start:ende], k)
        start = ende
        ende += batch_size
    result = result + translator(source[start:src_len], k)
    print("Time taken to predict k={}: {:.2f} sec".format(k, time.time() - set_off))

    return result


def translate_sentence(sentence, k=1, one_line=False):
    """translates sentence using beam search algorithm"""

    model, enc_output, dec_output, h, c = roll_out_encoder(sentence)
    first_pred = tf.math.top_k(dec_output, k)

    candidate_sentences = []
    for i in range(k):
        candidate_sentences.append(
            [
                [dic_tar.bi_dict["<s>"], get_value(first_pred.indices[0][0][i])],
                -math.log(get_value(first_pred.values[0][0][i])),
            ]
        )
    pred_values = []
    for index in range(1, max_line):
        all_candidates = []
        for j, _ in enumerate(candidate_sentences):
            pre_pred_word = candidate_sentences[j][0]
            if pre_pred_word[-1] == dic_tar.bi_dict["</s>"]:
                all_candidates.append(candidate_sentences[j])
                continue

            pre_sentence = tf.keras.preprocessing.sequence.pad_sequences(
                [pre_pred_word], maxlen=max_line, value=0, padding="post"
            )
            pred_word, _ = model.decoder((pre_sentence, enc_output), [h, c])

            k_best = tf.math.top_k(pred_word, k=k)

            seq, score = candidate_sentences[j]
            for x, _ in enumerate(k_best.indices):
                candidate = [
                    seq + [get_value(k_best.indices[0][index][x])],
                    score - math.log(get_value(k_best.values[0][index][x])),
                ]
                all_candidates.append(candidate)
        ordered = sorted(all_candidates, key=lambda tup: tup[1])
        candidate_sentences = ordered[:k]

    if one_line:
        for sen in candidate_sentences:
            print_sentence(sen[0])

    return candidate_sentences


# TODO translate with bigger batch_size dont forger remainder sentences
def beam_decoder(source, k, save=False):
    """finds the best translation scores using the beam decoder."""
    file_txt = []
    set_off = time.time()
    for i, src in enumerate(source):
        file_txt.append(translate_sentence(src, k))
    print("Time taken to predict k={}: {:.2f} sec".format(k, time.time() - set_off))
    # TODO add the blue metrik and print it.

    # save the predicted outputs
    if save:
        save_k_txt(file_txt, k)

    return file_txt


def rnn_pred_batch(source_list):
    """returns a batch from source file by padding all sentences"""
    for i, _ in enumerate(source_list):
        tmp = [
            dic_src.get_index(x)
            if x in dic_src.bi_dict
            else random.randint(0, len(dic_src.bi_dict) - 1)
            for x in source_list[i].split(" ")
        ]
        source_list[i] = tmp
    source_list = list(
        map(
            lambda x: [dic_src.bi_dict["<s>"]] + list(x) + [dic_src.bi_dict["</s>"]],
            source_list,
        )
    )
    # instead of maxlen=46 use max_word_in_line
    return tf.keras.preprocessing.sequence.pad_sequences(
        source_list, maxlen=max_line, value=0, padding="post"
    )


def print_sentence(pred):
    res = []
    keys = dic_tar.get_keys()
    for x in pred:
        res.append(keys[x])
    print(" ".join(res))


# TODO from terminal with runing with differnt model
def bleu_score(source, target, k=1, n=4):
    # plot best result by k
    set_off = time.time()
    x_achsis = []
    keys_list = dic_tar.get_keys()
    txt_list = []

    # run beam decoder and evaluate results
    source = rnn_pred_batch(source)
    print("Time taken to predict k={}: {:.2f} sec".format(k, time.time() - set_off))
    pred = fast_beam_search(source, k, 200)
    # pred = beam_decoder(source, k)
    # list of texts
    for elem in pred:
        # list of line string
        sentences = []
        for i in range(k):
            str_lines = [keys_list[x] for x in elem[i][0] if x > 2]
            sentence = " ".join(str_lines)
            sentences.append(sentence)
        txt_list.append(sentences)

    # save a string of best bleu results to save later
    results = []
    bleu_results = 0
    for i, top_k in enumerate(txt_list):
        best_bleu, indices = 0, 0
        for j, txt in enumerate(top_k):
            bleu = metrics.met_bleu([txt], [target[i]], n, False)
            if bleu > best_bleu:
                best_bleu = bleu
                indices = j
        results.append(top_k[indices])
        bleu_results += best_bleu
    print(metrics.met_bleu(results, target, n, False))
    # get avr bleu result
    bleu_results = round((bleu_results / len(results)), 2)
    return results, bleu_results


def get_enc_dec_paths():
    """returns encoder and decoder path as tuple"""
    enc_path = os.path.join(
        cur_dir,
        "rnn_checkpoints",
        "lstm_self_attention",
        "encoder.epoch09-loss0.12.hdf5",
    )
    dec_path = os.path.join(
        cur_dir,
        "rnn_checkpoints",
        "lstm_self_attention",
        "decoder.epoch09-loss0.12.hdf5",
    )

    return (enc_path, dec_path)


def main():
    """main method"""
    rnn.init_dics()
    source = read_from_file(
        os.path.join(cur_dir, "test_data", "multi30k.dev_subword.de")
    )
    target = read_from_file(os.path.join(cur_dir, "test_data", "multi30k.dev.en"))

    inputs = [
        "ein kleines kind steht allein auf einem zerklüfteten felsen .",
        "ein junge mit kopfhörern sitzt auf den schultern einer frau .",
        "ein brauner hund rennt dem schwarzen hund hinterher .",
    ]
    targ = [
        "a young child is standing alone on some jagged rocks .",
        "a boy wearing headphones sits on a woman &apos;s shoulders .",
        "a brown dog is running after the black dog .",
    ]
    # inputs = rnn_pred_batch(source)
    # translate_sentence(x, 1, True)
    # beam_decoder(inputs, 1, True)
    res, bleu = bleu_score(source, target, 5)
    save_translation(res, bleu)
    # print(fast_beam_search(source, 1, 200))
    # inputs = tf.convert_to_tensor(inputs)
    # print(inputs)
    # f, s = translate_line(1, inputs, 1)
    # print(f, s)


def rec_dec_tester():
    """called for testing specific methods"""
    rnn.init_dics()
    inputs = rnn_pred_batch(["ein mann schläft in einem grünen raum auf einem sofa ."])
    target = rnn_pred_batch(["a man sleeping in a green room on a couch ."])

    m = roll_out_encoder(None)


if __name__ == "__main__":
    main()
    # rec_dec_tester()
