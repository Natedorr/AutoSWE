# Source: https://developers.openai.com/codex/use-cases/budget-vs-actuals-review/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Review budget vs. actuals

Turn plan, actuals, and close notes into a variance workbook.Difficulty**Easy**Time horizon**30m**

Give Codex a budget, actuals export, and close notes, then ask it to map actuals to plan, calculate variances, flag reconciliation issues, and separate supported explanations from open finance questions.

## Best for

- Month-end reviews that compare budget plans with actual spend exports.
- Finance teams preparing leadership commentary from GL, spend, or department actuals.
- Workbooks where category mapping, tie-outs, and unsupported explanations need review.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/budget-vs-actuals-review/?export=pdf)

Give Codex a budget, actuals export, and close notes, then ask it to map actuals to plan, calculate variances, flag reconciliation issues, and separate supported explanations from open finance questions.Easy30m

Related linksAgent skills[Agent skills](/codex/skills)

## Best for

- Month-end reviews that compare budget plans with actual spend exports.
- Finance teams preparing leadership commentary from GL, spend, or department actuals.
- Workbooks where category mapping, tie-outs, and unsupported explanations need review.

## Skills & Plugins

- SpreadsheetsInspect spreadsheet inputs, clean and map rows, create variance tables, and produce reviewable workbook outputs.

Skill | Why use it
Spreadsheets | Inspect spreadsheet inputs, clean and map rows, create variance tables, and produce reviewable workbook outputs.

## Starter promptUse $spreadsheets to update the budget vs. actuals review from the attached files. Compare actuals to plan, map actuals to the right budget categories, summarize the major variances, and prepare a clean review view as an editable .xlsx workbook. Preserve the raw inputs, use formulas for dollar and percentage variance calculations, and flag categories that do not map cleanly instead of forcing a match. Use account type to determine favorable or unfavorable variance: revenue above plan is favorable, while expense above plan is unfavorable.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Use+%24spreadsheets+to+update+the+budget+vs.+actuals+review+from+the+attached+files.%0A%0ACompare+actuals+to+plan%2C+map+actuals+to+the+right+budget+categories%2C+summarize+the+major+variances%2C+and+prepare+a+clean+review+view+as+an+editable+.xlsx+workbook.%0A%0APreserve+the+raw+inputs%2C+use+formulas+for+dollar+and+percentage+variance+calculations%2C+and+flag+categories+that+do+not+map+cleanly+instead+of+forcing+a+match.+Use+account+type+to+determine+favorable+or+unfavorable+variance%3A+revenue+above+plan+is+favorable%2C+while+expense+above+plan+is+unfavorable.)Use $spreadsheets to update the budget vs. actuals review from the attached files. Compare actuals to plan, map actuals to the right budget categories, summarize the major variances, and prepare a clean review view as an editable .xlsx workbook. Preserve the raw inputs, use formulas for dollar and percentage variance calculations, and flag categories that do not map cleanly instead of forcing a match. Use account type to determine favorable or unfavorable variance: revenue above plan is favorable, while expense above plan is unfavorable.

## Introduction

If you’re working on a budget and want to review the variances or inspect any issues, Codex can help you create a fully functional review workbook you can work with.

Attach the budget plan, actuals export, and close notes, then ask Codex for an editable review workbook. Codex can preserve the raw inputs, map actuals to plan, calculate variances, and create a summary view you can inspect in the thread.Your browser does not support the video tag.

## Create the review workbook

- Attach the budget plan, actuals export, and close notes, or provide exact file references along with the source.
- Run the starter prompt and ask for an editable`.xlsx`workbook.
- Open the workbook in Codex. Expand it into the full-screen view to inspect the raw inputs, mappings, variance formulas, and summary tab.
- Continue in the same thread to fix category mappings, add department cuts, or draft the finance summary.

If the source files are in a connected app, mention the exact files or folder. Avoid asking Codex to search a broad Drive or workspace when the review should use specific finance sources. When the workbook appears in the thread, open it in Codex and expand it full-screen to review the raw inputs, mappings, variance formulas, and summary tab before asking for revisions.

## Check the variances

Before sharing the workbook, ask Codex to audit the categories, formulas, and variance explanations.Check the budget vs. actuals review before I share it. List: - the most material unfavorable variances by dollar impact - the most material favorable variances by dollar impact - categories that may be mapped incorrectly - accounts where the favorable or unfavorable sign convention is unclear - explanations supported by the close notes - explanations that need human review - formula or tie-out issues in the workbook Fix safe formatting or formula issues, then list anything finance should resolve before leadership review.

## Related use cases

### Forecast cash flow

Give Codex cash-flow inputs and model constraints, then ask it to create an editable...DataKnowledge Work[Forecast cash flowGive Codex cash-flow inputs and model constraints, then ask it to create an editable...DataKnowledge Work](/codex/use-cases/cash-flow-forecast)

### Model a DCF valuation

Attach historical financials, valuation assumptions, and modeling notes, then ask Codex for...DataKnowledge Work[Model a DCF valuationAttach historical financials, valuation assumptions, and modeling notes, then ask Codex for...DataKnowledge Work](/codex/use-cases/dcf-model)

### Clean and prepare messy data

Drag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work[Clean and prepare messy dataDrag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work](/codex/use-cases/clean-messy-data)