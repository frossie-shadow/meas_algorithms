# 
# LSST Data Management System
# Copyright 2008, 2009, 2010, 2011 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#
import numpy

import lsst.pex.config as pexConfig
import lsst.afw.table as afwTable
import lsst.pipe.base as pipeBase

from . import algorithmsLib
from .algorithmRegistry import *

__all__ = "SourceSlotConfig", "SourceMeasurementConfig", "SourceMeasurementTask"

class SourceSlotConfig(pexConf.Config):

    centroid = pexConf.Field(dtype=str, default="centroid.sdss", optional=True,
                             doc="the name of the centroiding algorithm used to set source x,y")
    shape = pexConf.Field(dtype=str, default="shape.sdss", optional=True,
                          doc="the name of the algorithm used to set source moments parameters")
    apFlux = pexConf.Field(dtype=str, default="flux.sinc", optional=True,
                           doc="the name of the algorithm used to set the source aperture flux slot")
    modelFlux = pexConf.Field(dtype=str, default="flux.gaussian", optional=True,
                           doc="the name of the algorithm used to set the source model flux slot")
    psfFlux = pexConf.Field(dtype=str, default="flux.psf", optional=True,
                            doc="the name of the algorithm used to set the source psf flux slot")
    instFlux = pexConf.Field(dtype=str, default="flux.gaussian", optional=True,
                             doc="the name of the algorithm used to set the source inst flux slot")

    def setupTable(self, table):
        """Convenience method to setup a table's slots according to the config definition.

        This is defined in the Config class to support use in unit tests without needing
        to construct a Task object.
        """
        if self.centroid is not None: table.defineCentroid(self.centroid)
        if self.shape is not None: table.defineShape(self.shape)
        if self.apFlux is not None: table.defineApFlux(self.apFlux)
        if self.modelFlux is not None: table.defineModelFlux(self.modelFlux)
        if self.psfFlux is not None: table.definePsfFlux(self.psfFlux)
        if self.instFlux is not None: table.defineInstFlux(self.instFlux)

class SourceMeasurementConfig(pexConf.Config):
    """
    Configuration for SourceMeasurementTask.
    A configured instance of MeasureSources can be created using the
    makeMeasureSources method.
    """

    slots = pexConf.ConfigField(
        dtype = SourceSlotConfig,
        doc="Mapping from algorithms to special aliases in Source.\n"
        )

    algorithms = AlgorithmRegistry.all.makeField(
        multi=True,
        default=["flags.pixel",
                 "centroid.gaussian", "centroid.naive",
                 "shape.sdss",
                 "flux.gaussian", "flux.naive", "flux.psf", "flux.sinc",
                 "classification.extendedness",
                 "skycoord",
                 ],
        doc="Configuration and selection of measurement algorithms."
        )
    
    centroider = AlgorithmRegistry.filter(CentroidConfig).makeField(
        multi=False, default="centroid.sdss", optional=True,
        doc="Configuration for the initial centroid algorithm used to\n"\
            "feed center points to other algorithms.\n\n"\
            "Note that this is in addition to the centroider listed in\n"\
            "the 'algorithms' field; the same name should not appear in\n"\
            "both.\n\n"\
            "This field DOES NOT set which field name will be used to define\n"\
            "the alias for source.getX(), source.getY(), etc.\n"
        )

    apCorrFluxes = pexConf.ListField(
        dtype=str, optional=False, default=["flux.psf", "flux.gaussian"],
        doc="Fields to which we should apply the aperture correction.  Elements in this list"\
            "are silently ignored if they are not in the algorithms list, to make it unnecessary"\
            "to always keep them in sync."
        )
    doApplyApCorr = pexConf.Field(dtype=bool, default=True, optional=False, doc="Apply aperture correction?")

    prefix = pexConf.Field(dtype=str, optional=True, default=None, doc="prefix for all measurement fields")

    def __init__(self):
        pexConf.Config.__init__(self)
        self.slots.centroid = self.centroider.name
        self.slots.shape = "shape.sdss"
        self.slots.psfFlux = "flux.psf"
        self.slots.apFlux = "flux.naive"
        self.slots.modelFlux = "flux.gaussian"
        self.slots.instFlux = "flux.gaussian"

    def validate(self):
        pexConf.Config.validate(self)
        if self.centroider.name in self.algorithms.names:
            raise ValueError("The algorithm in the 'centroider' field must not also appear in the "\
                                 "'algorithms' field.")
        if self.slots.centroid is not None and (self.slots.centroid not in self.algorithms.names
                                                and self.slots.centroid != self.centroider.name):
            raise ValueError("source centroid slot algorithm '%s' is not being run." % self.slots.astrom)
        if self.slots.shape is not None and self.slots.shape not in self.algorithms.names:
            raise ValueError("source shape slot algorithm '%s' is not being run." % self.slots.shape)
        for slot in (self.slots.psfFlux, self.slots.apFlux, self.slots.modelFlux, self.slots.instFlux):
            if slot is not None and slot not in self.algorithms.names:
                raise ValueError("source flux slot algorithm '%s' is not being run." % slot)

    def makeMeasureSources(self, schema, metadata=None):
        """ Convenience method to make a MeasureSources instance and
        fill it with the configured algorithms.

        This is defined in the Config class to support use in unit tests without needing
        to construct a Task object.
        """
        builder = algorithmsLib.MeasureSourcesBuilder(self.prefix if self.prefix is not None else "")
        if self.centroider is not None:
            builder.setCentroider(self.centroider.apply())
        builder.addAlgorithms(self.algorithms.apply())
        return builder.build(schema, metadata)

class SourceMeasurementTask(pipeBase.Task):
    """Measure the properties of sources on a single exposure.

    This task has no return value; it only modifies the SourceCatalog in-place.
    """
    ConfigClass = SourceMeasurementConfig

    def __init__(self, schema, algMetadata=None, **kwds):
        """Create the task, adding necessary fields to the given schema.

        @param[in,out] schema        Schema object for measurement fields; will be modified in-place.
        @param[in,out] algMetadata   Passed to MeasureSources object to be filled with initialization
                                     metadata by algorithms (e.g. radii for aperture photometry).
        @param         **kwds        Passed to Task.__init__.
        """
        pipeBase.Task.__init__(self, **kwds)
        self.measurer = self.config.makeMeasureSources(schema, algMetadata)
        if self.config.doApplyApCorr:
            self.fluxKeys = [(schema.find(f).key, schema.find(f + ".err").key)
                             for f in self.config.apCorrFluxes if f in self.config.algorithms.names]
            self.corrKey = schema.addField("aperturecorrection", type=float,
                                           doc="aperture correction factor applied to fluxes")
            self.corrErrKey = schema.addField("aperturecorrection.err", type=float,
                                              doc="aperture correction uncertainty")
        else:
            self.corrKey = None
            self.corrErrKey = None


    @pipeBase.timeMethod
    def run(self, exposure, sources, apCorr=None):
        """Run measure() and applyApCorr().

        @param[in]     exposure Exposure to process
        @param[in,out] sources  SourceCatalog containing sources detected on this exposure.
        @param[in]     apCorr   ApertureCorrection object to apply.

        @return None

        The aperture correction is only applied if config.doApplyApCorr is True and the apCorr
        argument is not None.
        """
        self.measure(exposure, sources)
        if self.config.doApplyApCorr and apCorr:
            self.applyApCorr(sources, apCorr)
    
    @pipeBase.timeMethod
    def measure(self, exposure, sources):
        """Measure sources on an exposure, with no aperture correction.

        @param[in]     exposure Exposure to process
        @param[in,out] sources  SourceCatalog containing sources detected on this exposure.
        @return None
        """
        self.config.slots.setupTable(sources.table)
        for record in sources:
            self.measurer.apply(record, exposure)

    @pipeBase.timeMethod
    def applyApCorr(self, sources, apCorr):
        self.log.log(self.log.INFO, "Applying aperture correction to %d sources" % len(sources))
        for source in sources:
            corr, corrErr = apCorr.computeAt(source.getX(), source.getY())
            for fluxKey, fluxErrKey in self.fluxKeys:
                flux = source.get(fluxKey)
                fluxErr = source.get(fluxErrKey)
                source.set(fluxKey, flux * corr)
                source.set(fluxErrKey, (fluxErr**2 * corr**2 + flux**2 * corrErr**2)**0.5)
            source.set(self.corrKey, corr)
            source.set(self.corrErrKey, corrErr)

