# Imports for file management, calculating ages and maths
from pathlib import Path
from datetime import date
import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "raw"

PROCESSED = ROOT / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)


def load_csv(filename):
    """Load a CSV from the project's data directory."""
    path = DATA / filename

    if not path.exists():
        raise FileNotFoundError(f"Could not find: {path}")

    print(f"Loading {filename}...")
    df = pd.read_csv(path, low_memory=False)
    print(f"  → {len(df):,} rows × {len(df.columns)} columns")

    return df


# ============================================================
# LOAD DATA
# ============================================================

countries = load_csv("primary/countries.csv")
countries["iso3"] = countries["iso3"].str.strip()

worldleaders = load_csv("primary/world_leaders.csv")
worldleaders["iso3"] = worldleaders["iso3"].str.strip()
worldleaders["dob"] = pd.to_datetime(worldleaders["dob"])

wpp_percentages = load_csv("secondary/wpp_percentages.csv")
wpp_percentages["ISO3_code"] = wpp_percentages["ISO3_code"].str.strip()

wpp_ex = load_csv("secondary/wpp_ex.csv")
wpp_ex["ISO3_code"] = wpp_ex["ISO3_code"].str.strip()
wpp_ex["Sex"] = wpp_ex["Sex"].str.strip()


# ============================================================
# REFERENCE DATE
# ============================================================

REFERENCE_DATE = date.today()


# ============================================================
# FUNCTIONS
# ============================================================

def calculate_age(dob, reference_date):
    """Calculate age in whole years on a given date."""
    return (
        reference_date.year
        - dob.year
        - (
            (reference_date.month, reference_date.day)
            < (dob.month, dob.day)
        )
    )


def calculate_median_age(country_population):
    """
    Calculate the median population age from single-age
    population percentages.

    The median is the age at which cumulative population
    reaches 50%.
    """

    age_groups = country_population.sort_values(
        "AgeGrpStart"
    ).copy()

    age_groups["CumulativePop"] = (
        age_groups["PopTotal"].cumsum()
    )

    median_match = age_groups[
        age_groups["CumulativePop"] >= 50
    ]

    if median_match.empty:
        raise ValueError(
            "Could not determine median population age."
        )

    median_age = median_match.iloc[0]["AgeGrpStart"]

    return float(median_age)


def calculate_ex_at_age(country_ex, age):
    """
    Get remaining life expectancy at a given age.

    WPP provides life expectancy in five-year age groups,
    so select the group containing the requested age.
    """

    ex_match = country_ex[
        country_ex["AgeGrpStart"] <= age
    ].sort_values("AgeGrpStart").tail(1)

    if ex_match.empty:
        raise ValueError(
            f"Could not find life expectancy for age {age}."
        )

    return float(ex_match["ex"].iloc[0])


def calculate_leader_metrics(iso3):
    """Calculate demographic metrics for a country's leader(s)."""

    # ========================================================
    # COUNTRY
    # ========================================================

    country_match = countries.loc[
        countries["iso3"] == iso3,
        "name"
    ]

    if country_match.empty:
        raise ValueError(
            f"No country found for ISO3: {iso3}"
        )

    country = country_match.iloc[0]


    # ========================================================
    # LEADERS
    # ========================================================

    # Get all leaders belonging to this country
    leader_match = worldleaders.loc[
        worldleaders["iso3"] == iso3
    ].copy()

    if leader_match.empty:
        raise ValueError(
            f"No leaders found for ISO3: {iso3}"
        )


    # ========================================================
    # LEADER AGES
    # ========================================================

    leader_ages = []

    for dob in leader_match["dob"]:
        leader_age = calculate_age(
            dob.date(),
            REFERENCE_DATE
        )

        leader_ages.append(leader_age)


    # Calculate mean age across all leaders
    mean_leader_age = sum(leader_ages) / len(leader_ages)


    # ========================================================
    # LEADER NAMES / DOBs
    # ========================================================

    # Use semicolons rather than commas because the output
    # file itself is comma-separated.
    leader_name_string = "; ".join(
        leader_match["leader_name"].tolist()
    )

    leader_dob_string = "; ".join(
        leader_match["dob"].dt.strftime("%Y-%m-%d").tolist()
    )


    # ========================================================
    # POPULATION AGE DISTRIBUTION
    # ========================================================

    country_population = wpp_percentages[
        (wpp_percentages["ISO3_code"] == iso3) &
        (wpp_percentages["Time"] == REFERENCE_DATE.year)
    ].copy()

    if country_population.empty:
        raise ValueError(
            f"No population data found for {iso3} "
            f"in {REFERENCE_DATE.year}"
        )


    # --------------------------------------------------------
    # Population median age
    # --------------------------------------------------------

    population_median = calculate_median_age(
        country_population
    )


    # --------------------------------------------------------
    # Percentage of population younger than mean leader age
    # --------------------------------------------------------

    population_younger = country_population[
        country_population["AgeGrpStart"] < mean_leader_age
    ]["PopTotal"].sum()


    # ========================================================
    # REMAINING LIFE EXPECTANCY
    # ========================================================

    country_ex = wpp_ex[
        (wpp_ex["ISO3_code"] == iso3) &
        (wpp_ex["Time"] == REFERENCE_DATE.year) &
        (wpp_ex["Sex"] == "Total")
    ].copy()

    if country_ex.empty:
        raise ValueError(
            f"No WPP life expectancy rows found for {iso3} "
            f"in {REFERENCE_DATE.year}"
        )


    # --------------------------------------------------------
    # Leader remaining life expectancy
    # --------------------------------------------------------

    leader_ex = calculate_ex_at_age(
        country_ex,
        mean_leader_age
    )


    # --------------------------------------------------------
    # Population remaining life expectancy
    # --------------------------------------------------------

    population_ex = calculate_ex_at_age(
        country_ex,
        population_median
    )


    # ========================================================
    # GAPS
    # ========================================================

    age_gap = mean_leader_age - population_median

    ex_gap = leader_ex - population_ex


    # ========================================================
    # RETURN METRICS
    # ========================================================

    return {
        "iso3": iso3,
        "country": country,

        "leader_name": leader_name_string,
        "leader_dob": leader_dob_string,

        "leader_age": round(
            mean_leader_age,
            1
        ),

        "population_median": round(
            population_median,
            1
        ),

        "leader_percentile": round(
            float(population_younger),
            3
        ),

        "leader_ex": round(
            leader_ex,
            3
        ),

        "population_ex": round(
            population_ex,
            3
        ),

        "age_gap": round(
            age_gap,
            1
        ),

        "ex_gap": round(
            ex_gap,
            3
        )
    }


# ============================================================
# CALCULATE METRICS FOR ALL COUNTRIES
# ============================================================

results = []

for iso3 in countries["iso3"]:
    results.append(
        calculate_leader_metrics(iso3)
    )


results = pd.DataFrame(results)


# ============================================================
# CALCULATE OLD FART INDEX
# ============================================================

results["ofi"] = (
    (
        (results["leader_percentile"] / 100)
        * ((5 - results["ex_gap"]) / 60)
    ) ** 0.5
)


# ============================================================
# OUTPUT
# ============================================================

results = results[
    [
        "iso3",
        "country",
        "leader_name",
        "leader_dob",
        "leader_age",
        "leader_percentile",
        "leader_ex",
        "population_median",
        "population_ex",
        "age_gap",
        "ex_gap",
        "ofi"
    ]
]


print("\nLeader metrics:")
print(results.to_string(index=False))


# ============================================================
# SAVE
# ============================================================

output_path = (
    PROCESSED / "ofi.csv"
)

results.to_csv(
    output_path,
    index=False
)

print(f"\nSaved to: {output_path}")