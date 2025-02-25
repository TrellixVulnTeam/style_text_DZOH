import time
import torch
import torch.nn.functional as F
from copy import deepcopy

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class BeamState(object):

    def __init__(self, word, h, sentence, nll):
        """
        Args:
            word -- the id of the word charachterising the state
            h -- the hidden state associated to that state
            sentence -- a list of word ids (the past ids plus the current one)
            nll -- the negative log likelihood corresponding to the sentence
        """
        self.word, self.h, self.sentence, self.nll = \
            word, h, sentence, nll


class BeamSearchDecoder(object):

    def __init__(self, styleTransfer, params):
        self.model = styleTransfer
        self.max_length = params.max_len
        self.width = params.beam_width
        self.params = params

    def _decode(self, tokens, h):
        """
        Args:
            tokens --
            h --
        Outputs:
            logProbs --
            indices --
            h --
        """
        currTokens = tokens
        currh = h
        # generate next h state and logit
        # generator needs input (seq_len, batch_size, input_size)
        outs, h = self.model.generator(currTokens, currh, pad=False)
        vocabLogits = self.model.hiddenToVocab(h)
        vocabLogits = vocabLogits[0]
        # smooth logits into the probabilities of each word
        vocabProbs = F.softmax(
            vocabLogits / self.params.temperature, dim=1)
        # beam search trick to prevent probs vanishing
        logProbs = torch.log(vocabProbs)
        # take the beam_with most probable words
        logProbs, indices = torch.topk(logProbs, self.width, dim=-1)
        return logProbs, indices, h

    def _beamDecode(self, h0):
        """
        Returning the ids of the beam_width most probable sentences' words.

        Args:
            h0 -- the first hidden state of dim = dim_y + dim_z
        """
        batch_size = h0.shape[1]
        go = ['<go>'] * batch_size
        init_state = BeamState(
            go,
            h0,
            [[] for i in range(batch_size)],
            [0]*batch_size)
        beam = [init_state]
        for _ in range(self.max_length):
            storeBeamLayer = [[] for _ in range(batch_size)]
            for state in beam:
                embs = self.model.vocabulary(state.word)
                embs = embs.unsqueeze(1)
                logProbs, indices, h = self._decode(embs, state.h)
                for b in range(batch_size):
                    for w in range(self.width):
                        word = self.model.vocabulary.id2word[int(indices[b, w])]
                        storeBeamLayer[b].append(
                            BeamState(word,
                                      h[:, b, :],
                                      state.sentence[b] + [indices[b, w]],
                                      state.nll[b] - logProbs[b, w]))

            beam = [init_state for _ in range(self.width)]
            for b in range(batch_size):
                # sort beam states by their probability (cumulated nll)
                # TODO check if performance increase by dividing nll
                # by number of words
                sortedBeamLayer = sorted(storeBeamLayer[b], key=lambda k: k.nll)
                for w in range(self.width):
                    beam[w].word[b] = sortedBeamLayer[w].word
                    beam[w].h[:, b, :] = sortedBeamLayer[w].h
                    beam[w].sentence[b] = sortedBeamLayer[w].sentence
                    beam[w].nll[b] = sortedBeamLayer[w].nll

        # Returning the ids of the beam_width most probable sentences' words.
        sentences = beam[0].sentence
        sentences = [
            [self.model.vocabulary.id2word[i] for i in sent]
            for sent in sentences]
        # TODO strip the EOS
        sentences = list(map(lambda x: " ".join(x), sentences))
        return sentences

    def rewriteBatch(self, sentences, labels):
        self.model.transformBatch(sentences, labels)
        originalHiddens = self.model.originalHiddens
        transformedHiddens = self.model.transformedHiddens
        original = self._beamDecode(originalHiddens)
        transformed = self._beamDecode(transformedHiddens)
        return original, transformed
