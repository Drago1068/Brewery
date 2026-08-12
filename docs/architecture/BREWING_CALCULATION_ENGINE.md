# Brewing Calculation Engine Specification

## Principle
Authoritative brewing calculations are deterministic, testable functions independent of the LLM.

## MVP Calculation Families
- unit conversions
- gravity points and extract contribution
- expected OG
- attenuation
- expected FG where model inputs permit
- ABV
- brewhouse/mash efficiency
- batch and recipe scaling
- strike water volume
- strike temperature
- total brewing liquor estimates
- color estimate
- bitterness estimate
- yeast pitch requirement
- carbonation / priming calculations
- basic brewing salt additions from explicit targets

## Later Calculation Families
- advanced water chemistry equilibrium
- detailed hop utilization by equipment/process
- yeast viability modeling
- dissolved oxygen models
- cost optimization
- statistical process capability

## Validation
Each formula family requires:
- documented formula/reference
- input domain
- units
- expected tolerance
- golden test cases
- edge-case tests

The AI may explain the result but cannot replace the calculation engine.
