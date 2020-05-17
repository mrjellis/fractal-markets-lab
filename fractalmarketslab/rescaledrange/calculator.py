import statistics
from scipy import stats
import math
from .functions import *
from .imports import *
from .export import exportFractal
import sys

# Fetch historical prices
ticker = "SP500"
asset_data = getApiData(ticker)

prices = extractData(asset_data, 'close')
count = len(prices)

# Arbitrary fractal scales
scales = exponentialScales(count, 3, 6)

print(json.dumps(scales, indent=1))

returns = returnsCalculator(prices)
deviations = deviationsCalculator(returns, scales)
running_totals = running_totalsCalculator(deviations, scales)

# Calculating statistics of returns and running totals
range_stats = {}
for scale, days in scales.items():
    range_stats[scale] = {}
    range_stats[scale]['means'] = chunkedAverages(returns, days)
    range_stats[scale]['stDevs'] = chunkedDevs(returns, days)
    range_stats[scale]['minimums'] = chunkedRange(running_totals[scale], days)['minimum']
    range_stats[scale]['maximums'] = chunkedRange(running_totals[scale], days)['maximum']
    range_stats[scale]['ranges'] = chunkedRange(running_totals[scale], days)['range']


# Calculating Rescale Range
for scale, values in range_stats.items():
    range_stats[scale]['rescaleRanges'] = {}
    for i, value in values['ranges'].items():
        rescaleRange = (value / values['stDevs'][i] if (values['stDevs'][i] != 0) else 0)

        range_stats[scale]['rescaleRanges'][i] = rescaleRange

# Key stats for fractal calculations
for scale, values in range_stats.items():
    range_stats[scale]['keyStats'] = {}
    rescaleRanges = list(values['rescaleRanges'].values())
    range_stats[scale]['keyStats']['rescaleRangeAvg'] = statistics.mean(rescaleRanges)
    range_stats[scale]['keyStats']['size'] = scales[scale]
    range_stats[scale]['keyStats']['logRR'] = math.log10(statistics.mean(rescaleRanges)) if (statistics.mean(rescaleRanges) > 0) else 0
    range_stats[scale]['keyStats']['logScale'] = math.log10(scales[scale])

# Hurst Exponent Calculations
fractal_results = {
    'rescaleRange': {}
}
# Adding rescale ranges to final data
for scale, days in scales.items():
    fractal_results['rescaleRange'][scale] = round(range_stats[scale]['keyStats']['rescaleRangeAvg'], 2)


# Calculating linear regression of rescale range logs
log_RRs = scaledDataCollector(scales, range_stats, ['keyStats', 'logRR'])
log_scales = scaledDataCollector(scales, range_stats, ['keyStats', 'logScale'])
slope, intercept, r_value, p_value, std_err = stats.linregress(log_scales, log_RRs)

# Calculator
def fractalSections(x, y):
    if len(x) != len(y):
        return "X and Y values contain disproportionate counts"

    fractal_scales = {
        'trade': {
            'x': list(backwardChunks(x, 2))[-1],
            'y': list(backwardChunks(y, 2))[-1],
        },
        'month': {
            'x': list(backwardChunks(x, 3))[-1],
            'y': list(backwardChunks(y, 3))[-1],
        },
        'trend': {
            'x': list(backwardChunks(x, 4))[-1],
            'y': list(backwardChunks(y, 4))[-1],
        },
        'tail': {
            'x': list(backwardChunks(x, 5))[-1],
            'y': list(backwardChunks(y, 5))[-1],
        },
    }
    return fractal_scales


def fractalCalculator(x, y):
    sections = fractalSections(x, y)
    results = {}
    for i, section in sections.items():
        slope, intercept, r_value, p_value, std_err = stats.linregress(section['x'], section['y'])
        results[i] = {
            'hurstExponent': round(slope, 2),
            'fractalDimension': round((2 - slope), 2),
            'r-squared': round(r_value**2, 2),
            'p-value': round(p_value, 2),
            'standardError': round(std_err, 2)
        }
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    results['fullSeries'] = {
        'hurstExponent': round(slope, 2),
        'fractalDimension': round((2 - slope), 2),
        'r-squared': round(r_value**2, 2),
        'p-value': round(p_value, 2),
        'standardError': round(std_err, 2)
    }
    return results


# Results
fractal_results['regressionResults'] = fractalCalculator(log_scales, log_RRs)
# print(json.dumps(fractal_results, indent=1))

# Export to CSV
exportFractal(fractal_results, scales)
