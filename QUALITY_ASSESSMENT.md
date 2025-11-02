# Forecast Quality Assessment

## Test Question
"Will there be a significant AI safety breakthrough in 2026?"

## Superforecaster Quality Checklist

### ✅ PASSED Criteria

1. **Base Rates Mentioned** ✅
   - Explicitly states: "Historical breakthroughs: RLHF (~2020), Constitutional AI (~2022), Mechanistic interp methods (~2021-2022)"
   - Calculates: "~35% chance per year based on ~1.5 breakthroughs per 3 years"
   - **Grade: A**

2. **Research Depth** ✅
   - Made 10 tool calls total:
     - 2x search_news (AskNews)
     - 1x web_research (Perplexity)
     - 7x WebSearch
   - Research covered: recent breakthroughs, funding trends, expert timelines, historical precedents
   - **Grade: A** (met 10+ requirement)

3. **Clear Reasoning** ✅
   - Detailed research summary with key findings
   - Transparent thought process
   - Evidence-backed conclusions
   - Example: "Anthropic mapped 30+ million features in Claude 3 Sonnet (May 2024)"
   - **Grade: A**

4. **Quantified Uncertainty** ✅
   - Model 1: 35%
   - Model 2: 51%
   - Model 3: 45%
   - Final: 46% (rounded from 45.6%)
   - Confidence level: "Moderate"
   - **Grade: A**

5. **Alternative Scenarios** ✅
   - Pros/cons for each model
   - Positive adjustments: funding growth, recent progress, industry focus
   - Negative adjustments: problem difficulty, high bar
   - **Grade: A**

6. **Calibration Awareness** ✅
   - States "moderate" confidence
   - Acknowledges "high bar for field-changing"
   - Notes "fundamental challenges remain"
   - **Grade: B+** (could be more specific about calibration)

### ⚠️ NEEDS IMPROVEMENT

1. **Number of Models** ⚠️
   - Generated: 3 models
   - Required: 5 models minimum
   - Missing model types:
     - Expert consensus model (aggregate Metaculus/forecaster predictions)
     - Reference class model (compare to other fields)
     - Monte Carlo/scenario analysis
   - **Grade: C** (only 60% of requirement)

2. **Model Diversity** ⚠️
   - Has: Base rate, momentum-adjusted, trajectory extrapolation
   - Missing:
     - Inside view (causal/mechanistic model)
     - Outside view (reference class)
     - Expert aggregation
     - Conditional scenarios
   - **Grade: B-** (good but could be more diverse)

3. **Squiggle Model Quality** ⚠️
   - All 3 models have Squiggle code in conversation
   - But extraction failed - trajectory.json shows fragments
   - Example bad extraction: `"name": "COMPARISON AND SELECTION"` (not a model name)
   - **Grade: C** (models exist but extraction is broken)

### ❌ FAILED Criteria

1. **Tool Call Logging** ❌
   - Conversation shows 10 tool calls
   - `tool_calls` array in trajectory: EMPTY
   - This is a tracking bug, not a quality issue
   - **Grade: F** (critical bug)

## Overall Assessment

### Strengths
1. **Excellent research depth**: 10 research calls with diverse sources
2. **Strong base rate analysis**: Historical data properly used
3. **Clear, evidence-backed reasoning**: Cites specific breakthroughs and data
4. **Proper uncertainty quantification**: Multiple probabilities with confidence level
5. **Transparent methodology**: Shows all calculations and assumptions

### Weaknesses
1. **Insufficient model count**: Only 3 models vs 5+ required
2. **Limited model diversity**: Missing expert aggregation, reference class, scenarios
3. **Broken Squiggle extraction**: Models exist but aren't captured properly
4. **Tool tracking bug**: Tool calls not logged in trajectory array

## Comparison to Superforecaster Reports

### Good Judgment Project Style
**What we have:**
- ✅ Base rates
- ✅ Multiple models
- ✅ Clear reasoning
- ✅ Cited sources

**What's missing:**
- ⚠️ More models (GJP typically uses 5-7)
- ⚠️ Scenario analysis (optimistic/pessimistic/baseline)
- ⚠️ Explicit calibration discussion

### Metaculus Top Forecaster Style
**What we have:**
- ✅ Technical depth
- ✅ Quantitative analysis
- ✅ Recent data integration

**What's missing:**
- ⚠️ Distribution estimates (not just point estimates)
- ⚠️ Update history (how forecast would change with new info)

## Scores by Category

| Category | Score | Weight | Weighted |
|----------|-------|--------|----------|
| Base Rates | A (95%) | 20% | 19.0% |
| Research Depth | A (95%) | 20% | 19.0% |
| Model Count | C (60%) | 15% | 9.0% |
| Model Diversity | B- (75%) | 15% | 11.25% |
| Clear Reasoning | A (95%) | 15% | 14.25% |
| Uncertainty | A (95%) | 10% | 9.5% |
| Calibration | B+ (85%) | 5% | 4.25% |

**Total Score: 86.25% (B+)**

## Gaps to Address

### Priority 1: Model Count (HIGH IMPACT)
**Issue**: Only 3 models instead of 5+

**Fix**: Update system prompt to require 5+ models with specific types:
```
You MUST create at least 5 models:
1. Base Rate Model - Historical frequency
2. Inside View Model - Causal/mechanistic reasoning
3. Outside View Model - Reference class comparison
4. Expert Consensus Model - Aggregate expert predictions
5. Trend Extrapolation Model - Current trends extended
6. (Optional) Monte Carlo Model - Multiple scenarios
7. (Optional) Conditional Model - Break down by conditions
```

### Priority 2: Squiggle Extraction (MEDIUM IMPACT)
**Issue**: Squiggle models not properly extracted from conversation

**Fix**: Improve regex in `_extract_models_and_forecast()`:
- Look for `### MODEL \d+:` pattern
- Extract everything between model headers
- Better identify code blocks with ```squiggle

### Priority 3: Tool Call Logging (LOW IMPACT - BUG)
**Issue**: Tool calls not appearing in trajectory.tool_calls array

**Fix**: The conversation shows tools were called, but logging failed. Check SystemMessage handling in enhanced_forecaster.py

### Priority 4: Model Diversity (MEDIUM IMPACT)
**Issue**: Missing key model types

**Fix**: Add model templates to prompt:
```
REQUIRED MODEL TYPES:
- Base Rate: Historical frequency analysis
- Inside View: Detailed causal model of mechanisms
- Outside View: Reference class (similar forecasts/fields)
- Expert Consensus: Survey/aggregate expert predictions
- Scenario Analysis: Optimistic/baseline/pessimistic
```

## Iteration Plan

### Iteration 1: Add Model Requirements
1. Update `ENHANCED_FORECASTER_PROMPT` to require 5+ models
2. Add specific model type requirements
3. Provide model templates with examples
4. Re-test

### Iteration 2: Fix Squiggle Extraction
1. Update `_extract_models_and_forecast()` regex
2. Better pattern matching for model sections
3. Preserve Squiggle code blocks
4. Re-test

### Iteration 3: Enhance Prompts
1. Add superforecaster examples
2. Emphasize calibration discussion
3. Request scenario analysis
4. Re-test

## Expected Improvement

After iterations:
- Model count: 3 → 5-7 (C → A)
- Model diversity: B- → A
- Squiggle extraction: C → A
- Overall score: 86% → 94% (A)

## Timeline

- Iteration 1: 10 minutes
- Iteration 2: 10 minutes
- Iteration 3: 10 minutes
- Final test: 5 minutes
- **Total: ~35 minutes**
