"""Numerical bodies preserved from PNAS code/analysis/source_helpers.py.
See PROVENANCE.md. No empirical data or source entry points are copied.
"""
import numpy as np

def findCorrespondingValue(xList, yList, findValue):
    xfit_max = 0
    for i in range(len(yList)):
        if yList[i] == findValue:
            xfit_max = xList[i]
        elif yList[i] == findValue:
            pass
    return xfit_max

def count_reversals_HighLow(contrastList):
    averageList = []
    TrialNumber = []
    countR      = 0
    checkSign   = 0
    signValue   = -1
    
    j           = 0
    
    if len(contrastList) > 1:
        if contrastList[j+1]-contrastList[j] < 0: # i.e. N12 - N10, then get  j-1
            signValue = -1
        elif contrastList[j+1]-contrastList[j] > 0: 
            signValue = 1
        elif contrastList[j+1]-contrastList[j] == 0: 
            pass
            
        checkSign = signValue
        j         = 0
        while j < len(contrastList)-2:
            j+=1
            if contrastList[j+1]-contrastList[j] < 0: # i.e. N12 - N10, then get  j-1
                signValue = -1
            elif contrastList[j+1]-contrastList[j] > 0: 
                signValue = 1
            elif contrastList[j+1]-contrastList[j] == 0: 
                pass
            
            if checkSign != signValue:
                checkSign = signValue 
                countR   += 1
                averageList.append(contrastList[j])
                TrialNumber.append(j)
            elif checkSign == signValue:
                pass
    elif len(contrastList) <= 1:
        TrialNumber=[1]
        TrialNumber=[0]
        averageList=[0] 
        
    return len(TrialNumber), TrialNumber, averageList

def makeList(xArray, func, **kwargs):
    newList = []
    for x in xArray:
        newList.append(func(x, **kwargs))
    return newList

def AoE(x, x0, x1, x2,x3):
    # a:x1 b:x0, f0:x3 , f1:x2
    X = x-x3
    return x0*np.exp(-(X))+(x1*np.exp(-pow((X)/x2,2)))

def fit_to_CSF(xNew, yNew, fitFunction,guessParams, BoundsDW_CSF,BoundsUP_CSF, n_fittingTries, fitRULE):

    #xLimMax         = [min(xNew), max(xNew)+10]
    xLimMax         = [0.1, max(xNew)+10]

    xy3         = fitFunctionLimit(xLimMax, xNew, yNew,fitFunction, guessParams, BoundsDW_CSF,BoundsUP_CSF, fitRULE, n_fittingTries)
    xfit_list3  = xy3[0]
    yfit_list3  = xy3[1]   
    paramsFIT   = xy3[2]

    xMax        = findCorrespondingValue(xfit_list3, yfit_list3, max(yfit_list3))  
          
    return xfit_list3, yfit_list3, paramsFIT, xMax

def fitFunctionLimit(xLimMax,xdata, ydata,function_fit,guessParams, boundDW, boundUP, fitm, fitNumber=10_000):
    from scipy.optimize import curve_fit
    
    maxX, minX      =  xLimMax[1], xLimMax[0]
    xStep           = (maxX - minX)/1000
    xdataContinuous = list(np.arange(minX, maxX,xStep) )
    params_totalFit = {}
    #try:  # lm, trf, dogbox 
    # fitm = 'lm'
    Rss, Tss, Rsquared= 0,0,0     
    if len(guessParams) > 1 and len(boundUP) > 1: 
        popt, pcov    = curve_fit(function_fit, xdata, ydata,p0=guessParams,method=fitm, maxfev=fitNumber, bounds=(boundDW, boundUP)) ## 20_000
    elif len(guessParams) <=1 and len(boundUP) > 1:
        popt, pcov    = curve_fit(function_fit, xdata, ydata,method=fitm, maxfev=fitNumber, bounds=(boundDW, boundUP)) ## 20_000
    elif len(guessParams) <=1 and len(boundUP) <= 1:
        popt, pcov    = curve_fit(function_fit, xdata, ydata,method=fitm, maxfev=fitNumber) 
    #nan_policy='omit'    
    for indexKey in range(len(popt)):
        params_totalFit.update({'x'+str(indexKey):popt[indexKey]})
        
    fitfunction_array = makeList(xdataContinuous, function_fit, **params_totalFit)


    return xdataContinuous, fitfunction_array, params_totalFit, pcov
