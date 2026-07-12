# StarsVisibility

StarsVisibility is a free web tool for estimating when stars and planets become visible to the unaided eye during twilight.

Live tool: https://starsvisibility.pages.dev/

## What it estimates

For a selected location, date, time, and object, the application estimates:

- object position and apparent altitude;
- solar depression and minutes after local sunset;
- atmospheric extinction and refraction;
- twilight, moonlight, and background-sky brightness;
- an approximate naked-eye limiting magnitude;
- first visibility, confidence, and likely limiting factors.

## Important limitation

The result is a calculated estimate, not a guarantee of what every observer will see. Transparency, haze, smoke, local horizon conditions, sky brightness, observer experience, target location, and stellar color can materially change the result. The project needs systematic field validation.

## How to help

The most useful contribution is a blinded observation:

1. Choose a specified star and location.
2. Do not look at the predicted time first.
3. Record when the star becomes continuously visible.
4. Record date, location, target, targeted versus free search, sky condition, and whether the observation was momentary or continuous.
5. Submit the report with the prediction still hidden.

Technical reviewers are also welcome to examine one focused assumption or benchmark case rather than attempting a complete review.

Please open an issue for a reproducible discrepancy, a scientific reference, a proposed test, or a code improvement.

Contact: starsvisibility@gmail.com
# starsvisibility
Open-source astronomy tool for estimating when stars and planets become visible during twilight.
