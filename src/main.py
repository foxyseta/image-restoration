import lib
import numpy as np
from skimage import metrics
from scipy.optimize import minimize as sciminimize
import matplotlib.pyplot as plt
import os
import sys

# Default MAXITER
MAXITER = 10

# Methods Dictionary
methods = {
    "naive" : { 
        "phi" : lambda _: 0,
        "dphi" : lambda _: 0
    },
    "tikhonov" : { 
        "phi" : lambda X: 0.5*np.linalg.norm(X)**2,
        "dphi" : lambda X: X
    },
    "tv" : { 
        "phi" : lib.totvar,
        "dphi" : lib.grad_totvar
    }
}

# Array of (kernel length, standard deviation)
blurs = ((5, 0.5), (7, 1), (9, 1.3))

# Function that implement gradient method
def minimize(x0,f,df,maxiter,abs_stop) -> np.ndarray: 

    #initialize first values
    x_last = np.zeros((x0.size))
    k=0

    # Stopping criteria 
    # k < maxiter -1 ( -1 because otherise returns out of bounds )
    while (np.linalg.norm(df(x_last))>abs_stop and k < maxiter-1):
        k=k+1
        grad = df(x_last)#direction is given by gradient of the last iteration

        # backtracking step
        step = lib.next_step(x_last,f,grad)

        if(step==-1):
            print('non convergente')
            return (k) #no convergence

        # calculate new x with 'step' as alpha and '-grad' as the direction
        x_last=x_last-step*grad

    return x_last

# read image data from file
def phase0(name):
    path = "img/" + name + ".png"
    img = plt.imread(path).astype(np.float64)
    return img

# Apply blur and noise then return the new image, PSF, PSNR and MSE
def phase1(img):
    bs = []
    # Iterate for each blurs
    for blur in blurs:
        # Generate a blurring filter
        K = lib.psf_fft(lib.gaussian_kernel(*blur), blur[0], img.shape)
        # Generate noise
        noise = np.random.normal(size=img.shape) * 0.05
        # Apply blur and noise
        b = lib.A(img, K) + noise
        PSNR = metrics.peak_signal_noise_ratio(img, b)
        MSE = metrics.mean_squared_error(img, b)
        bs.append((b, PSNR, MSE, K))

    return bs

def phasen(blurred, l, phi_dphi, minimize):
    b = blurred[0]
    method_fns =  f_generator(l, phi_dphi[0], phi_dphi[1])
    f, df = method_fns(blurred[3],b)
    return minimize(np.zeros(b.shape), f, df)


def phasen_multi(lambdas, blurred_images, method='naive', minFun='scipy'):
    deblurred = []
    phi_dphi = (methods[method]["phi"], methods[method]["dphi"])
    minimizeFun = sci_minimize if minFun == 'scipy' else our_minimize
    
    for l in lambdas:
        for blurred in blurred_images:
            deblurred.append(phasen(blurred, l, phi_dphi, minimizeFun))
    return deblurred

"""
    f_generator = f(l, regulating_term, regulating_term_grad) -> hardcode_f(K,b) -> (f,df)

    Generalization of function to minimize and of its derivative

    l = lambda
    regulating_factor = fn(X) -> matrix
    regulating_factor_grad = fn(X) -> matrix
"""
def f_generator(l, regulating_term, regulating_term_grad):
    def hardcode_f(K,b):
        def f(x):
            X = x.reshape(b.shape)
            #    |        same for every method        |     |   user choise  |
            res = 0.5*(np.linalg.norm(lib.A(X, K)-b)**2) + l*regulating_term(X)
            return np.sum(res)
        def df(x):
            X = x.reshape(b.shape)
            #    | same for every method |     |     user choise     |
            res = lib.AT(lib.A(X, K)-b, K) + l*regulating_term_grad(X)
            newRes = np.reshape(res, b.size)
            return newRes
        return (f,df)
    return hardcode_f

"""
    our_minimize = (x0, f, df) -> matrix
"""
def our_minimize(x0, f, df):
    return np.reshape(minimize(x0, f, df,MAXITER,MAXITER*2), x0.shape)

"""
    sci_minimize = (x0, f, df) -> matrix
"""
def sci_minimize(x0, f, df):
    return np.reshape(sciminimize(f, x0, method='CG', jac=df, options={'maxiter':MAXITER}).x, x0.shape)

def show_plt(file, method, lambdas, original, blurred_images, deblurred, figW=14, figH=7):
    len_l = len(lambdas)
    len_b = len(blurred_images)
    
    fig, axs = plt.subplots(len_l+2, len_b, constrained_layout=True, figsize=(figW, figH))
    fig.suptitle(f'Image = {file}\nMethod = {method}\nMAXITER = {MAXITER}', fontweight='bold', fontsize=18)

    for row, ax in enumerate(axs[:,:]):
        for col, tx in enumerate(ax[:]):
            if(row == 0):
                tx.set_title(f'Original')
                tx.imshow(original, cmap='gray', vmin=0, vmax=1)
            elif(row == 1):
                tx.set_title(f'σ={blurs[col][1]} , dim={blurs[col][0]}x{blurs[col][0]}')
                tx.imshow(blurred_images[col][0], cmap='gray', vmin=0, vmax=1)
            else:
                coord = (row-2)*(len_b) + col
                tx.set_title(f"Lambda={lambdas[row-2]}")
                tx.imshow(deblurred[coord], cmap='gray', vmin=0, vmax=1)

    plt.show()

if __name__ == "__main__":
    print("Esempio di esecuzione:\npython main.py [naive|tikhonov|tv] [our|scipy] (MAXITER) ( ... lambdas )")
    args = sys.argv[1:]
    if(len(args) == 0 or args[0] not in methods):
        print("Devi scegliere un methodo : naive | tikhonov | tv ")
        exit()

    method = args[0]
    minFun = 'scipy'

    if(len(args) > 1):
        minFun = args[1]
        if(minFun != 'scipy' and minFun != 'our'):
            print("La funzione di minimizzazione deve essere 'our' o 'scipy' !")
            exit()

    try:
        if(len(args) > 2):
            MAXITER = int(args[2])
    except:
        print("MAXITER deve essere un numero intero!")
        exit()

    # default lambdas
    lambdas = [1,2,3,4]
    try:
        if(len(args) > 3):
            lambdas = np.array(args[3:]).astype(float)
    except:
        print("Le λ devono essere numeri!")
        exit()

    # files = ['1', '2', '3', '4', '5', '6', '7', '8', 'A', 'B']
    files_os = os.listdir("img/")
    files = ['1']
    for file in files:
        # read image from file
        original = phase0(file)
        # execute phase1 and get blurred_images
        blurred_images = phase1(original)
        # execute with a regularization choosen with method param
        deblurred = phasen_multi(lambdas, blurred_images, method, minFun)

        show_plt(file, method, lambdas, original, blurred_images, deblurred)
