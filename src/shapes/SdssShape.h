#if !defined(LSST_MEAS_ALGORITHMS_SDSSSHAPE_H)
#define LSST_MEAS_ALGORITHMS_SDSSSHAPE_H 1
/**
 * @file
 */
#include "lsst/meas/algorithms/Shape.h"
#include "lsst/meas/algorithms/ShapeImpl.h"

namespace lsst { namespace meas { namespace algorithms {

/**
 * @brief A class that knows how to calculate centroids using the SDSS centroiding algorithm
 */
template<typename MaskedImageT>
class SdssMeasureShape : public MeasureShape<MaskedImageT> {
public:
    /**
     * @brief Return the (unique) instance of SdssMeasureShape
     */
    static MeasureShape<MaskedImageT>* getInstance() {
        if (_instance == NULL) {
            _instance = new SdssMeasureShape;
            MeasureShape<MaskedImageT>::registerType("SDSS", SDSS);
        }
        return _instance;
    }
private:
    SdssMeasureShape() {}
    Shape doApply(MaskedImageT const& image, double xcen, double ycen, PSF const*, double background) const;

    static SdssMeasureShape* _instance;
};
}}}
#endif
