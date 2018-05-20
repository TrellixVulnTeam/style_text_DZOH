from sklearn.utils import shuffle


def batchesFromFiles(files: list, batchsize: int, inMemory: bool):
    if inMemory:
        return loadFilesAndGenerateBatches(files, batchsize)

    return yieldBatchesFromFiles(files, batchsize)


def yieldBatchesFromFiles(files, batchsize):
    """
    Generate batches without loading files in memory
    """
    openedFiles = []
    for fname in files:
        openedFiles.append(open(fname, 'r'))

    while True:
        inputs = []
        labels = []
        for label, fp in enumerate(openedFiles):
            for i in range(batchsize // len(files)):
                # remove final '\n'
                inputs.append(fp.readline()[:-1])
                labels.append(label)

        yield inputs, labels


def loadFilesAndGenerateBatches(files, batchsize, shuffleFiles=True):
    inputs = []
    labels = []
    for label, fileName in enumerate(files):
        with open(fileName, 'r') as fp:
            lines = fp.readlines()

        labels.extend([label] * len(lines))
        inputs.extend(lines)

    if shuffleFiles:
        inputs, labels = shuffle(inputs, labels)

    batches = []
    for index in range(0, len(inputs), batchsize):
        batches.append(
            (inputs[index:index+batchsize],
             labels[index:index+batchsize]))

    return batches


def preprocessSentences(sentences):
    def addGo(sentence):
        out = ['<go>']
        out.extend(sentence)
        return out

    encoder_inputs = sentences
    decoder_inputs = list(map(addGo, sentences))
    targets = list(map(lambda x: x.append('<eos>'), sentences))
    return encoder_inputs, decoder_inputs, targets
