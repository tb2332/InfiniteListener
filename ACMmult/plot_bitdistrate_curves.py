"""
Code to analyze a set of experiments and automatically plot the
curves, and saves the data
"""

import os
import sys
import glob
import pickle
import numpy as np

import oracle_matfiles as ORACLE
import analyze_saved_model as ANALYZE
import model as MODEL



def plot_from_file(filename):
    """
    Plot the bitrate curves from the data sevd to file.
    Data must be between '#PLOTSTUFF' and '#PLOTDONE'
    """
    # import pylab
    import pylab as P

    # PARSE FILE
    f = open(filename,'r')
    # find beginning of data
    line = f.next()
    while line[:len('#PLOTSTUFF')] != '#PLOTSTUFF':
        line = f.next()
    bitrates = []
    bitrate = []
    # iterate over lines
    while True:
        line = f.next()
        if line[:len('#PLOTDONE')] == '#PLOTDONE':
            if len(bitrate) > 0:
                bitrates.append( bitrate )
            break
        if line[:len('#BITRATE')] == '#BITRATE':
            if len(bitrate) > 0:
                bitrates.append( bitrate )
            bitrate = []
            continue
        res = eval(line)
        bitrate.append( res )
    # close file
    f.close()

    # plotting symbols
    psymbs = ['-','--','-.',':','x-','o-','s-','+-','<-','>-']

    # create figure
    P.figure()
    P.hold(True)

    # iterate over bitrates
    idx = -1
    for bitrate in bitrates:
        idx += 1
        # smaller psize / number of codes
        min_psize = min(map(lambda x: x[0],bitrate))
        min_ncode = min(map(lambda x: x[1],bitrate))
        legend_str = 'psize='+str(min_psize)+', #codes='+str(min_ncode)
        # psize and values
        psizes = np.array(map(lambda x: x[0], bitrate))
        dists = np.array(map(lambda x: x[2], bitrate))
        order = np.argsort(psizes)
        psizes = psizes[order]
        dists = dists[order]
        # plot
        P.plot(psizes,dists,psymbs[idx],label=legend_str)
        
    # legend
    P.legend()
    # done, release, show
    P.hold(False)
    P.show()


def same_bitrate_curve(psize1,ncodes1,psize2,ncodes2):
    """
    Returns True or false, decides if two bit rates are the same or not.
    Meaning: when the psize is double, ncodes is squared. So, one of the
    psize is a multiple of a power of two of the other (2->4, 2->8,4->256,...)
    and the data is squared that many times (2->4 => ncordes*ncodes)
    """
    # trivial case
    if psize1 == psize2:
        if ncodes1 == ncodes2:
            return True
        return False
    # make sure psize1 is smaller: psize1 < psize2
    if psize1 > psize2:
        psize2,psize1 = psize1,psize2
        ncodes2,ncodes1 = ncodes1,ncodes2
    # other trivial case
    if ncodes2 < ncodes1:
        return False
    # REAL JOB STARTS HERE
    exponent = np.log2(psize2) - np.log2(psize1)
    if abs(exponent - np.round(exponent)) > 1e-10:
        return False
    exponent = int(np.round(exponent))
    # psize fits, now ncodes
    n1 = ncodes1
    for k in range(exponent):
        n1 = n1 * n1
    if n1 == ncodes2:
        return True
    return False


def check_saved_model_full(savedmodel,trim=True):
    """
    Returns True or False, check if a given saved model has all the
    files that we expect from it.
    If trim, remove that folder so we don't consider it later on.
    """
    ok = True
    expected_files = ['model.p','params.p','stats.p']
    variable_files = ['starttime_*.txt']
    # expected files
    for f in expected_files:
        if not os.path.exists(os.path.join(savedmodel,f)):
            ok = False
            break
    # variable files, files with *
    if ok:
        for f in variable_files:
            if len(glob.glob(os.path.join(savedmodel,f))) == 0:
                ok = False
                break
    # trim if required
    if trim and not ok:
        print 'triming folder',savedmodel,'because of missing files'
        shutil.rmtree(savedmodel)
    # done, retutn
    return ok



def analyze_one_exp_dir(expdir,validdir,testdir):
    """
    Analyze one experiment dir.
    This directory contains many subdirectory, for all the saved models.
    Check every saved model with validdata (numpy array), and test the
    best one on the test data.
    Returns numbers: patternsize, codebook size, distortion error, best saved model
    """
    # get all subdirs
    alldirs = glob.glob(os.path.join(expdir,'*'))
    if len(alldirs) > 0:
        alldirs = filter(lambda x: os.path.isdir(x), alldirs)
        alldirs = filter(lambda x: os.path.split(x)[-1][:4] == 'exp_',alldirs)
        # trim badly saved models
        alldirs = filter(lambda x: check_saved_model_full(x,False), alldirs)
    if len(alldirs) == 0:
        print 'no saved model found in:',expdir
        return None,None,None,None
    
    # get params
    savedmodel = np.sort(alldirs)[-1]
    params = ANALYZE.unpickle(os.path.join(savedmodel,'params.p'))

    # load valid data
    oracle = ORACLE.OracleMatfiles(params,validdir,oneFullIter=True)
    validdata = [x for x in oracle]
    validdata = filter(lambda x: x != None, validdata)
    validdata = np.concatenate(validdata)
    assert validdata.shape[1] > 0,'no valid data??'
    
    # load test data
    if validdir != testdir:
        oracle = ORACLE.OracleMatfiles(params,testdir,oneFullIter=True)
        testdata = [x for x in oracle]
        testdata = filter(lambda x: x != None, testdata)
        testdata = np.concatenate(testdata)
        assert testdata.shape[1] > 0,'no valid data??'
    else:
        testdata = validdata

    # test all subdirs with valid data, keep the best
    best_model = ''
    best_dist = np.inf
    for sm in alldirs:
        model = ANALYZE.unpickle(os.path.join(sm,'model.p'))
        codewords, dists = model.predicts(validdata)
        avg_dist = np.average(dists)
        if avg_dist < best_dist:
            best_model = sm
            best_dist = avg_dist
    assert best_model != '','no data found???'
    
    # test with test data
    model = ANALYZE.unpickle(os.path.join(best_model,'model.p'))
    codewords, dists = model.predicts(testdata)
    avg_dist = np.average(dists)
    print 'best model:',best_model,' ( dist =',avg_dist,')'

    # return patternsize, codebook size, distortion errror, best saved model
    return testdata.shape[1]/12, model._codebook.shape[0], avg_dist, best_model






def die_with_usage():
    """
    HELP MENU
    """
    print 'usage:'
    print '  python plot_bitdistrate_curves.py [FLAGS] <valid dir> <test dir> <output> <exp1> .... <expN>'
    print '  python plot_bitdistrate_curves.py -plot output'
    print 'PARAMS:'
    print ' <valid dir>    contains matfiles of validation set'
    print '  <test dir>    contains matfiles of test set'
    print '    <output>    filename to text file, something like results.txt'
    print '     <exp..>    path to experiment folder, "set2exp12" for instance'
    sys.exit(0)


if __name__ == '__main__':

    # help menu
    if len(sys.argv) < 3:
        die_with_usage()

    # flags
    plotfile = ''
    while True:
        if len(sys.argv) < 2:
            break
        elif sys.argv[1] == '-plot':
            plotfile = sys.argv[2]
            sys.argv.pop(1)
        else:
            break
        sys.argv.pop(1)
    if plotfile != '':
        print 'plotting from file:',plotfile
        plot_from_file(plotfile)
        sys.exit(0)
        
    # params
    validdir = sys.argv[1]
    testdir = sys.argv[2]
    output = sys.argv[3]
    expdirs = []
    for k in range(4,len(sys.argv)):
        expdirs.append( sys.argv[k] )
    print 'experiment dirs:', expdirs

    # analyze each experiment dir
    results = []
    for d in expdirs:
        print 'doing exp dir:',d
        res = analyze_one_exp_dir(d,validdir,testdir)
        if res != None and res[0] != None:
            results.append(res)
    print 'we have',len(results),'results.'

    # print to file, debug
    f = open(output,'w')
    f.write(str(results) + '\n')

    # organize the results
    bitrates = []
    while len(results) > 0:
        # get one res
        res = results.pop()
        # check if it belongs to one set
        belongs = False
        for bitrate in bitrates:
            ref = bitrate[0]
            if same_bitrate_curve(res[0],res[1],ref[0],ref[1]):
                bitrate.append(res)
                belongs = True
                break
        # does not belong to existing set? create new one
        if not belongs:
            bitrates.append( [res] )
    print 'bitrates found, we have',len(bitrates),'of them.'

    # print to file
    for bitrate in bitrates:
        f.write('********* ONE BITRATE **********\n')
        for res in bitrate:
            f.write('psize='+str(res[0]))
            f.write(', ncodes='+str(res[1]))
            f.write(', dist='+str(res[2]))
            f.write(', model='+res[3])
            f.write('\n')

    # now write stuff in an easy format to recreate the plot
    f.write('#PLOTSTUFF\n')
    for bitrate in bitrates:
        f.write('#BITRATE\n')
        for res in bitrate:
            f.write(str(res[0])+','+str(res[1])+','+str(res[2])+'\n')
    f.write('#PLOTDONE\n')

    # done with file, close output
    f.close()

    # plot
    plot_from_file(output)


