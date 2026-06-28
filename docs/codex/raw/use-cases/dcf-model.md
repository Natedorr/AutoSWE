# Source: https://developers.openai.com/codex/use-cases/dcf-model/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Model a DCF valuation

Turn financial inputs into an editable valuation workbook.Difficulty**Intermediate**Time horizon**30m**

Attach historical financials, valuation assumptions, and modeling notes, then ask Codex for an editable DCF workbook you can inspect and revise in Codex.

## Best for

- Analysts turning historical financials and assumptions into a DCF workbook.
- Finance teams that want to inspect and iterate on the workbook in Codex.
- Teams preparing a valuation model from source files.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/dcf-model/?export=pdf)

Attach historical financials, valuation assumptions, and modeling notes, then ask Codex for an editable DCF workbook you can inspect and revise in Codex.Intermediate30m

Related linksAgent skills[Agent skills](/codex/skills)File inputs[File inputs](/api/docs/guides/file-inputs)

## Best for

- Analysts turning historical financials and assumptions into a DCF workbook.
- Finance teams that want to inspect and iterate on the workbook in Codex.
- Teams preparing a valuation model from source files.

## Skills & Plugins

- SpreadsheetsCreate editable spreadsheet workbooks from attached inputs, formulas, and assumptions.

Skill | Why use it
Spreadsheets | Create editable spreadsheet workbooks from attached inputs, formulas, and assumptions.

## Starter promptUse $spreadsheets to build a DCF workbook for the company in the attached source files. Include explicit operating drivers for revenue growth, margins, capex, and working capital. Calculate unlevered free cash flow, WACC, terminal value, and enterprise value. If capital structure and diluted share count are provided, bridge to implied equity value and implied equity value per share. Use any assumptions included in the source files. If an assumption is missing, add a clearly labeled placeholder in the assumptions tab instead of hiding it in a formula. If full balance sheet or cash-flow statement inputs are missing, create the operating forecast needed for unlevered free cash flow and flag the missing statement inputs. Generate the result as an editable .xlsx workbook.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Use+%24spreadsheets+to+build+a+DCF+workbook+for+the+company+in+the+attached+source+files.%0A%0AInclude+explicit+operating+drivers+for+revenue+growth%2C+margins%2C+capex%2C+and+working+capital.+Calculate+unlevered+free+cash+flow%2C+WACC%2C+terminal+value%2C+and+enterprise+value.+If+capital+structure+and+diluted+share+count+are+provided%2C+bridge+to+implied+equity+value+and+implied+equity+value+per+share.%0A%0AUse+any+assumptions+included+in+the+source+files.+If+an+assumption+is+missing%2C+add+a+clearly+labeled+placeholder+in+the+assumptions+tab+instead+of+hiding+it+in+a+formula.+If+full+balance+sheet+or+cash-flow+statement+inputs+are+missing%2C+create+the+operating+forecast+needed+for+unlevered+free+cash+flow+and+flag+the+missing+statement+inputs.%0A%0AGenerate+the+result+as+an+editable+.xlsx+workbook.)Use $spreadsheets to build a DCF workbook for the company in the attached source files. Include explicit operating drivers for revenue growth, margins, capex, and working capital. Calculate unlevered free cash flow, WACC, terminal value, and enterprise value. If capital structure and diluted share count are provided, bridge to implied equity value and implied equity value per share. Use any assumptions included in the source files. If an assumption is missing, add a clearly labeled placeholder in the assumptions tab instead of hiding it in a formula. If full balance sheet or cash-flow statement inputs are missing, create the operating forecast needed for unlevered free cash flow and flag the missing statement inputs. Generate the result as an editable .xlsx workbook.

## Introduction

Codex can help you create a fully functional DCF workbook that you can inspect and revise.

It can use multiple files as context, including the historical financials, valuation assumptions, and any modeling notes. You can provide these files directly, or use file references when the inputs live in Google Drive or another connected source. If so, provide the exact file references, as it will be more effective than asking Codex to search through all of your files.Your browser does not support the video tag.

## Create the workbook

- Attach the historical financials, valuation assumptions, and any modeling notes, or provide exact file references along with the source.
- Run the starter prompt and ask for an editable`.xlsx`workbook.
- Open the generated workbook in Codex. Expand it into the full-screen view to inspect the model tabs, formulas, assumptions, and valuation summary.
- Continue in the same thread to check formula links, change assumptions, add scenarios, or tighten the model.

When the workbook appears in the thread, open it in Codex and expand it full-screen. Review the source inputs, forecast drivers, valuation outputs, and sensitivity tables, then ask Codex to revise the same workbook from there.

## Check the valuation

Before using the workbook, ask Codex to review the model like a finance teammate would: source tie-outs, formulas, hardcoded assumptions, and valuation outputs.Review the DCF workbook before I use it. Check: - historicals tied to the source files - forecast drivers and visible assumptions - formulas versus hardcoded values - unlevered free cash flow calculation - WACC, terminal value, enterprise value, and any equity-value bridge - sensitivity table formulas - missing capital structure, diluted share count, or assumptions that need human review Fix safe formatting or formula issues, then list anything I should review manually.

## Revise one assumption

After reviewing the workbook in Codex, ask for targeted revisions in the same thread. Change one driver at a time so the impact is easy to inspect.Update the DCF model so [revenue growth, EBITDA margin, WACC, terminal growth, or capex] uses [new assumption]. Keep the old assumption visible in a note, update dependent formulas, and tell me which tabs changed.

## Related use cases

### Forecast cash flow

Give Codex cash-flow inputs and model constraints, then ask it to create an editable...DataKnowledge Work[Forecast cash flowGive Codex cash-flow inputs and model constraints, then ask it to create an editable...DataKnowledge Work](/codex/use-cases/cash-flow-forecast)

### Review budget vs. actuals

Give Codex a budget, actuals export, and close notes, then ask it to map actuals to plan...DataKnowledge Work[Review budget vs. actualsGive Codex a budget, actuals export, and close notes, then ask it to map actuals to plan...DataKnowledge Work](/codex/use-cases/budget-vs-actuals-review)

### Clean and prepare messy data

Drag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work[Clean and prepare messy dataDrag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work](/codex/use-cases/clean-messy-data)