#! /usr/bin/env python3

import struct
import math

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from docopt import docopt
import numpy as np
from scipy.stats import multivariate_normal as gauss

import matplotlib
matplotlib.use('TKAgg')

def read_gmm(fileGMM):
    '''
       Reads the weights, means and convariances from a GMM
       stored using format "UPC: GMM V 2.0"
    '''

    header = b'UPC: GMM V 2.0\x00'

    try:
        with open(fileGMM, 'rb') as fpGmm:
            headIn = fpGmm.read(15)
    
            if headIn != header:
                print(f'ERROR: {fileGMM} is not a valid GMM file')
                exit(-1)

            numMix = struct.unpack('@I', fpGmm.read(4))[0]
            weights = np.array(struct.unpack(f'@{numMix}f', fpGmm.read(numMix * 4)))

            (numMix, numCof) = struct.unpack('@II', fpGmm.read(2 * 4))
            means = struct.unpack(f'@{numMix * numCof}f', fpGmm.read(numMix * numCof * 4))
            means = np.array(means).reshape(numMix, numCof)

            (numMix, numCof) = struct.unpack('@II', fpGmm.read(2 * 4))
            invStd = struct.unpack(f'@{numMix * numCof}f', fpGmm.read(numMix * numCof * 4))
            covs = np.array(invStd).reshape(numMix, numCof) ** -2

            return weights, means, covs
    except:
        raise Exception(f'Error al leer el fichero {fileGMM}')


def read_fmatrix(fileFM):
    '''
       Reads an fmatrix from a file
    '''
    try:
        with open(fileFM, 'rb') as fpFM:
            (numFrm, numCof) = struct.unpack('@II', fpFM.read(2 * 4))
            data = struct.unpack(f'@{numFrm * numCof}f', fpFM.read(numFrm * numCof * 4))
            data = np.array(data).reshape(numFrm, numCof)

            return data
    except:
        raise Exception(f'Error al leer el fichero {fileFM}')


def pdfGMM(X, weights, means, covs):
    '''
       Returns the probability density function (PDF) of a population X
       given a Gaussian Mixture Model (GMM) defined by its weights,
       means and covariances.
    '''

    pdf = np.zeros(len(X))
    for mix, weight in enumerate(weights):
        try:
            pdf += weight * gauss.pdf(X, mean=means[mix], cov=covs[mix])
        except:
            raise Exception(f'Error al calcular la mezcla {mix} del GMM')

    return pdf

def limsGMM(means, covs, fStd=3):
    '''
       Returns the maximum and minimum values of the mean plus/minus fStd
       times the standard deviation for a set of Gaussians defined by their
       means and convariances.
    '''

    numMix = len(means)

    min_ = means[0][:]
    max_ = means[0][:]

    for mix in range(numMix):
        min_ = np.min((min_, means[mix] - fStd * covs[mix] ** 0.5), axis=0)
        max_ = np.max((max_, means[mix] + fStd * covs[mix] ** 0.5), axis=0)

    margin = max(max_ - min_)

    return min_, max_

def plotGMM(fileGMM, xDim, yDim, percents, colorGmm, filesFeat=None, colorFeat=None, limits=None, subplot=111):
    weights, means, covs = read_gmm(fileGMM)

    ax = plt.subplot(subplot)
    if filesFeat:
        feats = np.ndarray((0, 2))
        for fileFeat in filesFeat:
            feat = read_fmatrix(fileFeat)
            feat = np.stack((feat[..., xDim], feat[..., yDim]), axis=-1)
            feats = np.concatenate((feats, feat))

        ax.scatter(feats[:, 0], feats[:, 1], .05, color=colorFeat)

    means = np.stack((means[..., xDim], means[..., yDim]), axis=-1)
    covs = np.stack((covs[..., xDim], covs[..., yDim]), axis=-1)

    if not limits:
        min_, max_ = limsGMM(means, covs)
        limits = (min_[0], max_[0], min_[1], max_[1])
    else:
        min_, max_ = (limits[0], limits[2]), (limits[1], limits[3])

    # Fijamos el número de muestras de manera que el valor esperado de muestras
    # en el percentil más estrecho sea 1000. Calculamos el más estrecho como el
    # valor mínimo de p*(1-p)

    numSmp = int(np.ceil(np.max(1000 / (percents * (1 - percents))) ** 0.5))

    x = np.linspace(min_[0], max_[0], numSmp)
    y = np.linspace(min_[1], max_[1], numSmp)
    X, Y = np.meshgrid(x, y)

    XX = np.array([X.ravel(), Y.ravel()]).T

    Z = pdfGMM(XX, weights, means, covs)
    Z /= sum(Z)
    Zsort = np.sort(Z)
    Zacum = Zsort.cumsum()
    levels = [Zsort[np.where(Zacum > 1 - percent)[0][0]] for percent in percents]

    Z = Z.reshape(X.shape)

    style = {'colors': [colorGmm] * len(percents), 'linestyles': ['dotted', 'solid']}

    CS = ax.contour(X, Y, Z, levels=levels, **style)
    fmt = {levels[i]: f'{percents[i]:.0%}' for i in range(len(levels))}
    ax.clabel(CS, inline=1, fontsize=14, fmt=fmt)

    # plt.title(f'Region coverage predicted by {fileGMM}')
    speaker = fileGMM.rsplit('/', 1)[-1].rsplit('.', 1)[0]	
    plt.title(f'GMM/LOC (MFCC): {speaker}')
    plt.axis('tight')
    plt.axis(limits)
    plt.show()

def plotGMM_subplots(fileGMM, xDim, yDim, percents, colorGmm, filesFeat=None, limits=None):
    """
    Plot GMM subplots for comparison of different speakers.

    Parameters:
    - fileGMM: List of file paths to GMM files
    - xDim: Dimension index for x-axis
    - yDim: Dimension index for y-axis
    - percents: List of percentiles for contour plotting
    - colorGmm: List of colors for GMM plots
    - filesFeat: List of file paths to feature files (optional)
    - limits: Axis limits for plots (optional)
    """

    # Dictionary to store GMM data
    gmms = {}
    for i, gmm_file in enumerate(fileGMM):
        weights, means, covariances = read_gmm(gmm_file)
        gmms[i] = (weights, means, covariances)

    # Create subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
    
    if filesFeat:
        # Read and stack features
        features = np.ndarray((0, 2))
        for feat_file in filesFeat:
            feat = read_fmatrix(feat_file)
            feat = np.stack((feat[..., xDim], feat[..., yDim]), axis=-1)
            features = np.concatenate((features, feat))

        # Distribute features among subplots 1, 2, 3, and 4
        end_1 = math.floor(features.shape[0] / 2)
        ax1.scatter(features[:end_1, 0], features[:end_1, 1], 0.05, color=colorGmm[0])
        ax3.scatter(features[:end_1, 0], features[:end_1, 1], 0.05, color=colorGmm[0])
        ax2.scatter(features[end_1:, 0], features[end_1:, 1], 0.05, color=colorGmm[1])
        ax4.scatter(features[end_1:, 0], features[end_1:, 1], 0.05, color=colorGmm[1])

    speaker_left = fileGMM[0].rsplit('/', 1)[-1].rsplit('.', 1)[0]
    speaker_right = fileGMM[1].rsplit('/', 1)[-1].rsplit('.', 1)[0]

    # Process each GMM and plot contours
    for i, (weights, means, covariances) in enumerate(gmms.values()):
        first_ax = ax1 if i == 0 else ax3
        second_ax = ax2 if i == 0 else ax4

        means = np.stack((means[..., xDim], means[..., yDim]), axis=-1)
        covariances = np.stack((covariances[..., xDim], covariances[..., yDim]), axis=-1)

        if not limits:
            min_, max_ = limsGMM(means, covariances)
            limits = (min_[0], max_[0], min_[1], max_[1])
        else:
            min_, max_ = (limits[0], limits[2]), (limits[1], limits[3])

        # Determine number of samples based on percentiles
        num_samples = int(np.ceil(np.max(1000 / (percents * (1 - percents))) ** 0.5))
        x = np.linspace(min_[0], max_[0], num_samples)
        y = np.linspace(min_[1], max_[1], num_samples)
        X, Y = np.meshgrid(x, y)
        XX = np.array([X.ravel(), Y.ravel()]).T

        # Calculate the GMM PDF
        Z = pdfGMM(XX, weights, means, covariances)
        Z /= sum(Z)
        Zsort = np.sort(Z)
        Zacum = Zsort.cumsum()
        levels = [Zsort[np.where(Zacum > 1 - percent)[0][0]] for percent in percents]

        Z = Z.reshape(X.shape)
        style = {'colors': [colorGmm[0] if i == 0 else colorGmm[1]] * len(percents), 'linestyles': ['dotted', 'solid']}

        # Plot contours on both axes
        CS1 = first_ax.contour(X, Y, Z, levels=levels, **style)
        CS2 = second_ax.contour(X, Y, Z, levels=levels, **style)
        fmt = {levels[i]: f'{percents[i]:.0%}' for i in range(len(levels))}
        first_ax.clabel(CS1, inline=1, fontsize=14, fmt=fmt)
        second_ax.clabel(CS2, inline=1, fontsize=14, fmt=fmt)

        speaker = fileGMM[i].rsplit('/', 1)[-1].rsplit('.', 1)[0]
        first_ax.set_title(f'GMM: {speaker}, LOC: {speaker_left}')
        first_ax.axis('tight')
        first_ax.axis(limits)

        second_ax.set_title(f'GMM: {speaker}, LOC: {speaker_right}')
        second_ax.axis('tight')
        second_ax.axis(limits)

    fig.suptitle('Comparación modelos GMM LOC 7 y 130 para LPCC')
    plt.tight_layout()
    plt.subplots_adjust(top=0.85)
    plt.show()


########################################################################################################
# Main Program
########################################################################################################

USAGE='''
Draws the regions in space covered with a certain probability by a GMM.

Usage:
    plotGMM [--help|-h] [options] <file-gmm> [<file-feat>...]

Options:
    --xDim INT, -x INT               'x' dimension to use from GMM and feature vectors [default: 0]
    --yDim INT, -y INT               'y' dimension to use from GMM and feature vectors [default: 1]
    --percents FLOAT..., -p FLOAT...  Percentages covered by the regions [default: 90,50]
    --colorGMM STR, -g STR            Color of the GMM regions boundaries [default: red]
    --colorFEAT STR, -f STR           Color of the feature population [default: red]
    --limits xyLimits -l xyLimits     xyLimits are the four values xMin,xMax,yMin,yMax [default: auto]

    --help, -h                        Shows this message

Arguments:
    <file-gmm>    File with the Gaussian mixture model to be plotted
    <file-fear>   Feature files to be plotted along the GMM
'''

if __name__ == '__main__':
    args = docopt(USAGE)

    fileGMM = args['<file-gmm>']
    filesFeat = args['<file-feat>']
    xDim = int(args['--xDim'])
    yDim = int(args['--yDim'])
    percents = args['--percents']
    if percents:
        percents = percents.split(',')
        percents = np.array([float(percent) / 100 for percent in percents])
    colorGmm = args['--colorGMM']
    colorFeat = args['--colorFEAT']
    limits = args['--limits']
    if limits != 'auto':
        limits = [float(limit) for limit in limits.split(',')]
        if len(limits) != 4:
            print('ERROR: xyLimits must be four comma-separated values')
            exit(1)
    else:
        limits = None

    # Condicional para usar opción de gráfico simple o múltiple
    if filesFeat[0][-4:] == ".gmm":
        # Uso de subplots con plot_gmm_feat

        # Parseo de GMMs
        fileGMM = [fileGMM, filesFeat[0]]
        filesFeat = filesFeat[1:]

        # Llamada a la función plotGMM_subplots
        plotGMM_subplots(fileGMM, xDim, yDim, percents, colorGmm.split(), filesFeat, limits)
    else:
        # Uso regular de plot_gmm_feat (gráfico simple)
        plotGMM(fileGMM, xDim, yDim, percents, colorGmm, filesFeat, colorFeat, limits, 111)

