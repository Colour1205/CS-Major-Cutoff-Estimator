# Core prediction logic — estimates required csc148/csc165 average from historical + enrollment data.
from scipy.stats import beta as beta_dist

from backend.config import CSC148_AVG, CSC165_AVG, CSC165_ESTIMATED_SD_PCT, TOTAL_CS_SPOTS

# Keys expected in each year's merged data dict (enrollment_data.csv columns
# plus historical_averages.csv columns — see enrollment.py / estimate_service.py).
CSC111_WINTER = "csc111_winter"
CSC165_WINTER = "csc165_winter"
ACTUAL_CUTOFF = "actual_cutoff"


class Estimator:
    def __init__(self, data):
        # data: {year: {"csc111_winter": ..., "csc165_winter": ..., "actual_cutoff": ..., ...}}
        self.data = data

    @staticmethod
    def _beta_params_from_mean_std(mean_pct: float, std_pct: float) -> tuple[float, float]:
        """Moment-match a Beta(alpha, beta) distribution on [0, 1] to the
        given mean/std (both as % of 100).

        Beta is a natural fit for marks: it's bounded to [0, 1] by
        construction (no impossible >100%/<0% results, unlike a plain
        normal), and — crucially — whenever the mean sits above the
        midpoint (as course averages do), the moment-matched Beta comes out
        LEFT-skewed on its own: mass concentrated toward the higher end with
        a longer tail down toward lower marks. That's the real shape of a
        grades distribution, and it falls out of just fixing mean/std — no
        separate, hand-picked skew parameter needed.
        """
        mean = mean_pct / 100
        variance = (std_pct / 100) ** 2
        common = mean * (1 - mean) / variance - 1
        alpha = mean * common
        beta_param = (1 - mean) * common
        return alpha, beta_param

    def _normal_cutoff_estimate(self, applicants: int, spots: int) -> float:
        """Estimate the combined csc148/csc165 average needed to admit `spots`
        students out of `applicants`, assuming that average follows a Beta
        distribution across applicants — moment-matched to mean
        (CSC148_AVG + CSC165_AVG) / 2 and std dev CSC165_ESTIMATED_SD_PCT
        (see config.py for how that std dev was derived). See
        _beta_params_from_mean_std for why Beta specifically (bounded +
        naturally left-skewed, matching how grades are actually distributed).

        This is the inverse-CDF (percent point function): the score above
        which only `spots / applicants` of the distribution falls.
        """
        if applicants <= 0:
            return 0.0
        if spots >= applicants:
            return 0.0  # everyone who applies gets in — no effective cutoff

        mean = (CSC148_AVG + CSC165_AVG) / 2
        std = CSC165_ESTIMATED_SD_PCT
        admit_fraction = spots / applicants
        target_percentile = 1 - admit_fraction

        alpha, beta_param = self._beta_params_from_mean_std(mean, std)
        return float(beta_dist.ppf(target_percentile, alpha, beta_param) * 100)

    def _year_estimate(self, year_data: dict) -> float:
        csc111_winter = int(year_data[CSC111_WINTER])
        csc165_winter = int(year_data[CSC165_WINTER])

        # Everyone in csc111 instream is assumed admitted, so the remaining
        # spots go to the csc148 -> csc165 out-of-stream applicant pool.
        out_of_stream_spots = TOTAL_CS_SPOTS - csc111_winter

        # Everyone in csc165 is assumed to apply for CS, and since csc165
        # enrollment < csc148 enrollment, csc165 students have already taken
        # csc148 — so csc165_winter is the out-of-stream applicant pool.
        return self._normal_cutoff_estimate(csc165_winter, out_of_stream_spots)

    def estimate_cutoff(self) -> float:
        """Estimate the required csc148/csc165 average for the most recent
        (target) year — i.e. the highest year present in self.data. This is
        meant to be a year that either hasn't happened yet or whose actual
        cutoff isn't known yet; see estimate_service.load_merged_data for how
        that target year gets chosen/forecasted.

        Key idea:
        - estimate a raw cutoff for every OTHER year based on the seat-math +
          distribution model, and see how far off each one was from that
          year's real actual_cutoff
        - average those errors, and apply the average as a correction to the
          target year's raw estimate

        The target year is deliberately excluded from the error-averaging
        step even if it happens to have a known actual_cutoff on record
        (e.g. when re-running this for a past/already-resolved year, such as
        during backtesting) — otherwise the correction would be partly
        fitted to the very answer it's supposed to be predicting.
        """
        years = sorted(self.data.keys())
        if not years:
            raise ValueError("no historical data to estimate from")

        target_year = years[-1]

        errors = []
        for year in years:
            if year == target_year:
                continue  # never calibrate a year's estimate using its own known answer
            year_data = self.data[year]
            actual_cutoff = year_data.get(ACTUAL_CUTOFF)
            if actual_cutoff in (None, ""):
                continue  # no historical cutoff to compare against for this year
            estimated = self._year_estimate(year_data)
            errors.append(estimated - float(actual_cutoff))

        avg_error = sum(errors) / len(errors) if errors else 0.0

        target_estimate = self._year_estimate(self.data[target_year])

        return target_estimate - avg_error

    def estimate_safe_grade(self, actual_cutoff_by_year: dict, safe_grade_by_year: dict) -> float:
        """Estimate the "safe" grade for the most recent year.

        The bare cutoff (estimate_cutoff) can be misleading: the person
        right at the cutoff may have only gotten in because of a strong
        supplementary application, so plenty of other people at that exact
        grade get rejected. The "safe grade" instead tracks the grade
        cluster reported most often among people who did get in (e.g. "low
        90s" showing up repeatedly) — a much safer bet than the bare
        minimum.

        For every year with both an actual_cutoff and a safe_grade on
        record, computes distance = safe_grade - actual_cutoff, averages
        those distances, then adds that average on top of
        estimate_cutoff()'s calibrated prediction for the most recent year.

        actual_cutoff_by_year/safe_grade_by_year are passed in directly
        (rather than read from self.data) since the years with enough
        scraped reports to trust a safe-grade estimate don't necessarily
        overlap with the years that have enrollment data in self.data.
        """
        distances = []
        for year, safe_grade in safe_grade_by_year.items():
            actual_cutoff = actual_cutoff_by_year.get(year)
            if actual_cutoff in (None, ""):
                continue
            distances.append(float(safe_grade) - float(actual_cutoff))

        avg_distance = sum(distances) / len(distances) if distances else 0.0
        return self.estimate_cutoff() + avg_distance
