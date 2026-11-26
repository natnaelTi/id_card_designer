"""Ethiopian Amete Mihret calendar, using the ICU CE-calendar Julian-day epoch.

Reference: unicode-org/icu icu4c/source/i18n/ethpccal.cpp and cecal.cpp.
Date values entering Frappe's Date field are Gregorian; conversion is explicit.
"""

from datetime import date

EPOCH = 1723856


def ethiopian_to_gregorian(year, month, day):
    year, month, day = int(year), int(month), int(day)
    if (
        not 1 <= year <= 9000
        or not 1 <= month <= 13
        or not 1 <= day <= (6 if month == 13 and year % 4 == 3 else 5 if month == 13 else 30)
    ):
        raise ValueError("Invalid Ethiopian calendar date.")
    jd = EPOCH + 365 * year + year // 4 + 30 * (month - 1) + day - 1
    return date.fromordinal(jd - 1721425)


def gregorian_to_ethiopian(value):
    value = date.fromisoformat(str(value)[:10])
    jd = value.toordinal() + 1721425
    year = (4 * (jd - EPOCH) + 1463) // 1461
    while ethiopian_to_gregorian(year, 1, 1) > value:
        year -= 1
    while ethiopian_to_gregorian(year + 1, 1, 1) <= value:
        year += 1
    elapsed = (value - ethiopian_to_gregorian(year, 1, 1)).days
    return year, elapsed // 30 + 1, elapsed % 30 + 1


def format_ethiopian(value):
    if not value:
        return ""
    year, month, day = gregorian_to_ethiopian(value)
    return f"{day:02d} / {month:02d} / {year:04d} E.C."
