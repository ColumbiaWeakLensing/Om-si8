#!/usr/bin/env python

import sys,os
sys.modules["mpi4py"] = None

import lenstools

from lenstools.pipeline.simulation import SimulationBatch,LensToolsCosmology
from lenstools.pipeline.settings import EnvironmentSettings,NGenICSettings,PlaneSettings,CatalogSettings
from lenstools.pipeline.remote import LocalGit
from lenstools.simulations.camb import CAMBSettings
from lenstools.simulations.gadget2 import Gadget2Settings

import numpy as np
import astropy.units as u
from astropy.cosmology import z_at_value

git = LocalGit()

#Settings
camb = CAMBSettings()
ngenic = NGenICSettings()
gadget2 = Gadget2Settings()
planes = PlaneSettings.read("../planes.ini")
catalog = CatalogSettings.read("../catalog.ini")

zmax = 3.1
box_size_Mpc_over_h = 240.0
nside = 512
lens_thickness_Mpc = 80.0

#NGenIC
ngenic.GlassFile = lenstools.data("dummy_glass_little_endian.dat")

#Gadget
gadget2.NumFilesPerSnapshot = 16

#Init batch
if "--git" in sys.argv:
	batch = SimulationBatch.current(syshandler=git)
else:
	batch = SimulationBatch.current()

if "--tree" in sys.argv:

	#Add all the models,collections and one realization
	seed = np.random.randint(10000000)

	p = np.load("../../data/Om-si8.npy")
	d = list()

	for Om,si8 in p:
	
		#Lay down directory tree
		cosmo = LensToolsCosmology(Om0=Om,Ode0=1-Om,w0=-1.,sigma8=si8)
		model = batch.newModel(cosmo,parameters=["Om","Ol","si"])
		collection = model.newCollection(box_size=box_size_Mpc_over_h*model.Mpc_over_h,nside=nside)
		r = collection.newRealization(seed)

		#Plane and catalog directories
		pln = r.newPlaneSet(planes)
		ct = collection.newCatalog(catalog)


if "--camb" in sys.argv:

	#CAMB settings
	for model in batch.available:
		collection = model.collections[0]
		collection.writeCAMB(z=np.array([0.0]),settings=camb)


if ("--lenses" in sys.argv) or ("--pfiles" in sys.argv):

	#Compute comoving distance to maximum redshift for each model
	d = list()
	for model in batch.available:
		d.append(model.cosmology.comoving_distance(zmax))

	#Compute lens spacings
	d = np.array([dv.value for dv in d]) * d[0].unit

	#We want to make sure there are lenses up to the maximum of these distances
	lens_distances = np.arange(lens_thickness_Mpc,d.max().to(u.Mpc).value + lens_thickness_Mpc,lens_thickness_Mpc) * u.Mpc

	for model in batch.available:

		#Compute the redshifts of the Gadget snapshots
		z = np.zeros_like(lens_distances.value)
		for n,dlens in enumerate(lens_distances):
			z[n] = z_at_value(model.cosmology.comoving_distance,dlens)

		#Assgn values to gadget settings
		gadget2.OutputScaleFactor = np.sort(1/(1+z))

		if "--pfiles" in sys.argv:
		
			collection = model.collections[0]

			#Convert camb power spectra into ngenic ones
			collection.camb2ngenic(z=0.0)

			r = collection.realizations[0]

			#ngenic parameter file
			r.writeNGenIC(ngenic)

			#Gadget parameter file
			r.writeGadget2(gadget2)

		else:
			print(gadget2.OutputScaleFactor)
