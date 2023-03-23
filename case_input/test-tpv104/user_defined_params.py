#! /usr/bin/env python3

import numpy as np
from math import *
from lib  import *

# mode 
mode   = 1  # perform individual dynamic ruptures 
#mode   = 2  # serve in earthquake cycles

# model_domain (in meters)
xmin, xmax   = -22.0e3, 22.0e3
ymin, ymax   = -10.0e3, 12.0e3
zmin, zmax   = -22.0e3, 0.0e3

# fault geometry (in meters)
fxmin, fxmax = -18.0e3, 18.0e3
fymin, fymax = 0.0e3,   0.0e3    # for vertical strike-slip faults, we align faults along xz planes.
fzmin, fzmax = -18.0e3, 0.0e3 

xsource, ysource, zsource = 0.0, 0.0, -7.5e3

dx           = 400.0e0 # cell size, spatial resolution
nuni_y_plus  = 5 # along the fault-normal dimension, the number of cells share the dx cell size.
nuni_y_minus = 5 
enlarging_ratio = 1.025e0 # along the fault-normal dimension (y), cell size will be enlarged at this ratio compoundly.

#################################
#####  Material property   ######
#################################
nmat = 1 # 1: isotropic; >1: layered. 
# nmat: number of layers

if nmat == 1: 
    # only Vp, Vs, rou, 3 (n2mat) are needed.
    n2mat = 3 
    # Vp, Vs, Rou
    vp, vs, rou = 6.0e3, 3.464e3, 2.67e3
elif nmat > 1: 
    n2mat = 4
    mat = np.zeros((nmat, n2mat))
    # example here 1D velocity structure for the Cushing earthquake.
    mat[0,:] = [1.19e3,  2.74e3, 1.45e3, 2.1e3] # top layer
    mat[1,:] = [2.01e3,  5.75e3, 3.06e3, 2.4e3] # 2nd layer going downwards into the earth.
    mat[2,:] = [4.94e3,  5.72e3, 3.4e3,  2.6e3] # 3rd
    mat[3,:] = [10.94e3, 6.18e3, 3.62e3, 2.8e3] # 4th
    mat[4,:] = [-zmin,   6.32e3, 3.67e3, 2.8e3] # rest
    print(mat)

init_norm = -25.0e6 # initial normal stress in Pa. Negative compressive.

# total simulation time and dt
term        = 10.
dt          = 0.008*dx/100.

# Controlling switches for EQquasi system
C_elastic   = 1 # elastic(1).
C_nuclea    = 1 # artificial nucleation (1), no (0). 
C_degen     = 0 # degenerate hexahedrals (1), no (0).
friclaw     = 4 # sw(1), tw(2), rsf_aging(3), rsf_slip(4), rsf_slip_srw(5).
ntotft      = 1 # number of total faults.
nucfault    = 1 # the fault id of nucleation fault. Should be no larger than ntotft
rough_fault = 0 # include rough fault yes(1) or not(0).
nt_out      = 20 # Every nt_out time steps, disp of the whole model and on-fault variables will be written out in netCDF format.
tpv         = 104 
# Control outputs
output_plastic = 0
outputGroundMotion = 0 # output big vel GM time series for all the surface stations?

# currently supported cases
# 104  (SCEC-TPV104)
# 105  (SCEC-TPV1053D)
# 2801 (DRV)
# 1001 (GM-cycle)
#################################
########## Nucleation ###########
#################################

nucR       = 3.e3   # nucleation patch radius, m
nucRuptVel = -9999. # nucleation rupture velocity, m/s; useful for sw and tw.
nucdtau0   = 45.0e6 # peak shear stress increase for TPV104 and 105, Pa; useful for rsf

#################################
##### Frictional variables ######
#################################
# friclaw == 1, slip weakening
fric_sw_fs      = 0.18
fric_sw_fd      = 0.12
fric_sw_D0      = 0.3
# parameters needed for rsf.
# friclaw == 3/4, rsf with the aging law/slip law.
fric_rsf_a      = 0.01 
fric_rsf_b      = 0.014
fric_rsf_Dc     = 0.4
fric_rsf_deltaa = 0.01
fric_rsf_r0     = 0.6
fric_rsf_v0     = 1e-6
# additional parameters for friclaw == 5, rsf with the slip law and strong rate weakening.
fric_rsf_fw     = 0.2
fric_rsf_vw     = 0.1
fric_rsf_deltaavw0 = 0.9
# additional parameters for thermal pressurization. 
fric_tp_a_th    = 1.0e-6  # m^2/s
fric_tp_rouc    = 2.7e6   # J/(m^3K)
fric_tp_lambda  = 0.1e6   # paK^-1
fric_tp_h       = 0.02  # m
fric_tp_a_hy    = 4.0e-4  # m^2/s
fric_tp_deltaa_hy0 = 1.0 # m^2/s
fric_tp_Tini    = 483.15  # K
fric_tp_pini    = 80.0e6  # Pa

creep_slip_rate = 1e-16   # m/s
#################################
#####   Initial stresses   ######
#################################

#init_norm       = -120.0e6

# Creating the fault interface
nfx     = int((fxmax - fxmin)/dx + 1)
nfz     = int((fzmax - fzmin)/dx + 1)
fx      = np.linspace(fxmin,fxmax,nfx) # coordinates of fault grids along strike.
fz      = np.linspace(fzmin,fzmax,nfz) # coordinates of fault grids along dip.

# Create on_fault_vars array for on_fault varialbes.
on_fault_vars = np.zeros((nfz,nfx,100))
# functions are defined in lib.py under scripts/
# function lists:
# - shear_steady_state
# - state_steady_state
# - B1, defined in TPV104 and TPV105
# - B2 and B3, defined in TPV105
  
for ix, xcoor in enumerate(fx):
  for iz, zcoor in enumerate(fz):
  # assign a in RSF. a is a 2D distribution.
    on_fault_vars[iz,ix,1]   = fric_sw_fs 
    on_fault_vars[iz,ix,2]   = fric_sw_fd
    on_fault_vars[iz,ix,3]   = fric_sw_D0
    on_fault_vars[iz,ix,7]   = -120.0e6     # initial normal stress. Negative compressive.
    on_fault_vars[iz,ix,8]   = 40.0e6       # initial shear stress.
    
    tmp1  = B1(xcoor, 15.e3, 3.e3)
    tmp2  = B1(-zcoor-7.5e3, 15.e3/2., 3.e3)
    on_fault_vars[iz,ix,9]  = fric_rsf_a + (1. - tmp1*tmp2)*fric_rsf_deltaa
    on_fault_vars[iz,ix,10] = fric_rsf_b # assign b in RSF 
    on_fault_vars[iz,ix,11] = fric_rsf_Dc # assign Dc in RSF.
    #if (xcoor<=-18e3 and xcoor>=-30e3 and zcoor<=-4e3 and zcoor>=-16e3):
    #  on_fault_vars[iz,ix,11] = minDc # a special Dc zone.
    on_fault_vars[iz,ix,12] = fric_rsf_v0 # initial reference slip rate.
    on_fault_vars[iz,ix,13] = fric_rsf_r0 # initial reference friction.
    
    on_fault_vars[iz,ix,14] = fric_rsf_fw # 
    on_fault_vars[iz,ix,15] = fric_rsf_vw  + fric_rsf_deltaavw0*(1. - tmp1*tmp2)  # 
    on_fault_vars[iz,ix,16] = fric_tp_a_hy + fric_tp_deltaa_hy0*(1. - tmp1*tmp2)  #
    on_fault_vars[iz,ix,17] = fric_tp_a_th
    on_fault_vars[iz,ix,18] = fric_tp_rouc
    on_fault_vars[iz,ix,19] = fric_tp_lambda
    on_fault_vars[iz,ix,40] = fric_tp_h
    on_fault_vars[iz,ix,41] = fric_tp_Tini
    on_fault_vars[iz,ix,42] = fric_tp_pini
    
    on_fault_vars[iz,ix,46] = creep_slip_rate # initial slip rates
    #if (xcoor<=-18e3 and xcoor>=-30e3 and zcoor<=-4e3 and zcoor>=-16e3):
    #  on_fault_vars[iz,ix,46] = 0.03 # initial high slip rate patch.
    
    on_fault_vars[iz,ix,20] = state_steady_state(on_fault_vars[iz,ix,9], 
                                                on_fault_vars[iz,ix,10],
                                                on_fault_vars[iz,ix,11],
                                                on_fault_vars[iz,ix,12],
                                                on_fault_vars[iz,ix,13],
                                                on_fault_vars[iz,ix,8],
                                                on_fault_vars[iz,ix,7],
                                                on_fault_vars[iz,ix,46],
                                                friclaw) # initial state var.
    
    
###############################################
##### Domain boundaries for transferring ######
###############################################
xmin_trans, xmax_trans = -25e3, 25e3
zmin_trans = -25e3
ymin_trans, ymax_trans = -5e3, 5e3
dx_trans = 50 

####################################
##### HPC resource allocation ######
####################################
casename = str(tpv)
nx = 2
ny = 2
nz = 1

HPC_ncpu  = nx*ny*nz # Number of CPUs requested.
HPC_nnode = int(floor(HPC_ncpu/128)) + 1 # Number of computing nodes. On LS6, one node has 128 CPUs.
HPC_queue = "normal" # q status. Depending on systems, job WALLTIME and Node requested.
HPC_time  = "00:10:00" # WALLTIME, in hh:mm:ss format.
HPC_account = "EAR22013" # Project account to be charged SUs against.
HPC_email = ""#"dliu@ig.utexas.edu" # Email to receive job status.

##############################################
##### Single station time series output ######
##############################################

# (x,z) coordinate pairs for on-fault stations (in km).
st_coor_on_fault = [[0.0, -3.0], [0.0,-7.5], [0.0, -12.0], [9.0,-7.5], \
   [12.0, -3.0], [12.0,-12.0], [15.0, -7.5], [18.0,-7.5], [-9.0,-7.5], \
   [-12.0,-3.0], [-12.0,-12.0], [-15.0, -7.5], [-18.0, -7.5]]
   
# (x,y,z) coordinates for off-fault stations (in km).
st_coor_off_fault = [[0,9,0], [0,-9,0], [12,6,0], [12,-6,0], [-12,6,0], \
   [-12,-6,0]]
n_on_fault  = len(st_coor_on_fault)
n_off_fault = len(st_coor_off_fault)



