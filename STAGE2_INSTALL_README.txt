PSYVIEW CUSTOM EQUATION FITTING — STAGE 2
=========================================

Built against current green main baseline:
bf9386ecfb5ffc1700b149f98131831e18f5a3f0
("gpt update equation interface")

INSTALL
-------
1. CLOSE PsyView.
2. Extract this ZIP into the ROOT of Access_PNAS_psy_data.
3. Double-click:
       INSTALL_FIT_FUNCTION_STAGE2.bat
4. Wait for:
       INSTALL SUCCESSFUL
5. Start PsyView normally:
       run_psyview.bat

The installer does NOT use pytest locally. It syntax-checks/import-checks the
changes, rejects an unsafe expression, and performs a synthetic numerical fit.
If any of those checks fail, all live target files are restored automatically.

QUICK TEST
----------
Open the LATERAL dataset and go to Subject -> Luminance.

Press G.

Equation:
    A*cos(2*pi*f*x+phi)+C

Parameters:
    A=0.2[-2,2]; f=3[0.1,20]; phi=0[-pi,pi]; C=0[-2,2]

Press Enter in the equation field, then Enter in the parameter field.

The right panel should say that the ACTIVE FIT is Custom.

Press F. The red curve should now fit the custom equation to the CURRENT
displayed profile.

Press G then Ctrl+R to restore the specialist thesis Eq. B.25 fitter.

IMPORTANT SCIENTIFIC/SAFETY BEHAVIOUR
-------------------------------------
- Existing fit_lateral_profile() / thesis Eq. B.25 code is not modified.
- No custom function selected -> F uses the existing specialist Eq. B.25 fitter.
- Custom function selected -> F uses a separate generic custom fitter.
- Only the current displayed profile is fitted.
- Hidden sibling plots remain empirical-only for shared-axis calculations.
- Custom fit-point exclusions still work and are session-only.
- Custom curves have role='fit', so automatic axes remain empirical-driven.
- The same lateral weighting is used: sigma=max(full recorded spread, 0.05).
- Custom fits report fitted parameters, R^2, RMSE and weighted RMS.
- FMS is intentionally not reported for arbitrary custom equations.
- Custom functions and parameter settings are session-only.
- No empirical repository files are written.
- No GitHub files are written by the installer.
- Python eval() and exec() are never used for equations.

EQUATION LANGUAGE
-----------------
Use explicit multiplication (*).

Supported:
    +  -  *  /  ^
    sin cos tan
    sinh cosh tanh
    exp log ln log10 sqrt
    abs sign sgn
    pi e
    x
    user parameter names

Some LaTeX-like forms are accepted:
    \sin \cos \exp \sqrt \pi \lambda \phi |x|

Use "lam" rather than the Python keyword "lambda" in parameter definitions.

Parameter syntax:
    name=starting_value[lower_bound,upper_bound]

Example damped cosine:
    A*exp(-lam*abs(x))*cos(2*pi*f*x+phi)

    A=0.2[-2,2]; lam=1[0.001,10]; f=3[0.1,20]; phi=0[-pi,pi]

x is distance from the flanker edge in degrees.
With cos(2*pi*f*x), f is naturally cycles/degree.
With cos(k*x), k is angular spatial frequency in radians/degree.

DEVELOPMENT NOTE
----------------
This Stage-2 installer is only for applying the feature to Alexander's current
working checkout before it is committed. Once committed, ordinary users still
only need:

    download/extract repo -> double-click run_psyview.bat -> PsyView opens
