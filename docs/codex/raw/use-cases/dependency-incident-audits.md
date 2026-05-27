# Source: https://developers.openai.com/codex/use-cases/dependency-incident-audits/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Audit dependency incidents

Turn a public package advisory into a safe repo-audit plan.Difficulty**Advanced**Time horizon**1h**

Use Codex to turn a public package or supply chain advisory into a read-only audit, then inspect manifests, lock files, CI workflows, and scripts without running untrusted code.

## Best for

- Engineering and security teams responding to public package or supply chain advisories.
- Maintainers who need to check lock files, scripts, CI permissions, and caches before changing dependencies.
- Incident reviews where Codex should gather evidence without installing packages or running untrusted code.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/dependency-incident-audits/?export=pdf)

Use Codex to turn a public package or supply chain advisory into a read-only audit, then inspect manifests, lock files, CI workflows, and scripts without running untrusted code.Advanced1h

Related linksCodex Security[Codex Security](/codex/security)Agent approvals and security[Agent approvals and security](/codex/agent-approvals-security)Codex cyber safety[Codex cyber safety](/codex/concepts/cyber-safety)

## Best for

- Engineering and security teams responding to public package or supply chain advisories.
- Maintainers who need to check lock files, scripts, CI permissions, and caches before changing dependencies.
- Incident reviews where Codex should gather evidence without installing packages or running untrusted code.

## Skills & Plugins

- GitHub[GitHub](/codex/integrations/github)Inspect repository files, pull requests, workflows, and security-relevant history.

Skill | Why use it
GitHub[GitHub](/codex/integrations/github) | Inspect repository files, pull requests, workflows, and security-relevant history.

## Starter promptHelp me audit this repository for exposure to this public package advisory: [advisory URL]. Stay read-only unless I explicitly approve a remediation step. First, summarize: - affected packages and version ranges - authoritative sources versus broader reports - what evidence would prove exposure in this repo - what evidence would rule it out Then inspect: - package manifests and lock files - CI workflows and permissions - install, build, and postinstall scripts - vendored artifacts, containers, or generated bundles if relevant - cache or token exposure paths if the advisory involves CI or publishing Return: - evidence status: confirmed exposure, needs verification, or ruled out - severity and blast-radius notes - file references for every repo-specific claim - caveats and recommended next steps Do not install packages, run lifecycle scripts, build the project, execute untrusted code, rotate credentials, or clean up files unless I explicitly approve that step.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Help+me+audit+this+repository+for+exposure+to+this+public+package+advisory%3A+%5Badvisory+URL%5D.%0A%0AStay+read-only+unless+I+explicitly+approve+a+remediation+step.%0A%0AFirst%2C+summarize%3A%0A-+affected+packages+and+version+ranges%0A-+authoritative+sources+versus+broader+reports%0A-+what+evidence+would+prove+exposure+in+this+repo%0A-+what+evidence+would+rule+it+out%0A%0AThen+inspect%3A%0A-+package+manifests+and+lock+files%0A-+CI+workflows+and+permissions%0A-+install%2C+build%2C+and+postinstall+scripts%0A-+vendored+artifacts%2C+containers%2C+or+generated+bundles+if+relevant%0A-+cache+or+token+exposure+paths+if+the+advisory+involves+CI+or+publishing%0A%0AReturn%3A%0A-+evidence+status%3A+confirmed+exposure%2C+needs+verification%2C+or+ruled+out%0A-+severity+and+blast-radius+notes%0A-+file+references+for+every+repo-specific+claim%0A-+caveats+and+recommended+next+steps%0A%0ADo+not+install+packages%2C+run+lifecycle+scripts%2C+build+the+project%2C+execute+untrusted+code%2C+rotate+credentials%2C+or+clean+up+files+unless+I+explicitly+approve+that+step.)Help me audit this repository for exposure to this public package advisory: [advisory URL]. Stay read-only unless I explicitly approve a remediation step. First, summarize: - affected packages and version ranges - authoritative sources versus broader reports - what evidence would prove exposure in this repo - what evidence would rule it out Then inspect: - package manifests and lock files - CI workflows and permissions - install, build, and postinstall scripts - vendored artifacts, containers, or generated bundles if relevant - cache or token exposure paths if the advisory involves CI or publishing Return: - evidence status: confirmed exposure, needs verification, or ruled out - severity and blast-radius notes - file references for every repo-specific claim - caveats and recommended next steps Do not install packages, run lifecycle scripts, build the project, execute untrusted code, rotate credentials, or clean up files unless I explicitly approve that step.

## Start with a safe audit plan

When a dependency or supply chain incident moves quickly, the first useful output isn’t a rushed patch. It’s a clear audit plan: what changed, which packages or workflows might be affected, and what evidence would prove exposure in your repo.

Use Codex to turn the advisory into a conservative, read-only checklist before installing, building, testing, or running anything.

## Keep the first pass read-only

- Give Codex the public advisory, incident report, or affected package list.
- Ask it to separate authoritative sources from broader commentary.
- Have it define evidence that would prove or rule out exposure.
- Let it inspect manifests, lock files, CI workflows, scripts, and relevant repo files.
- Ask for findings grouped by evidence status, severity, and recommended next step.

For package incidents, avoid running install, build, test, import, or lifecycle commands until you know what the advisory affects. Codex can search lock files and workflows without executing untrusted code.

## Report evidence status separately from severity

A useful audit result should show both how bad a finding would be and how strong the evidence is:Codex

**Confirmed exposure:**the lockfile contains an affected package version in a production dependency path.

**Needs verification:**one CI job has publish permissions, but the workflow does not appear to install the affected package directly.

**Ruled out:**the package name appears in docs only and is not present in manifests or lock files.

**Next step:**review the proposed dependency update and token rotation plan before any destructive action.

Once the read-only pass is complete, you can ask Codex to prepare a remediation PR, update CI permissions, or write a follow-up incident note. Keep those actions separate from the initial audit.Turn the confirmed findings from this audit into a remediation plan. For each finding, include: - proposed change - files or settings to update - test or verification step - rollback plan - whether I need to rotate a credential or review an external system Do not make changes yet. Keep any command that could execute untrusted code out of the plan unless you explain why it is safe.

## Related use cases

### Add evals to your AI application

Ask Codex to inspect your AI application, identify the behavior you want to evaluate, and...EvaluationQuality[Add evals to your AI applicationAsk Codex to inspect your AI application, identify the behavior you want to evaluate, and...EvaluationQuality](/codex/use-cases/ai-app-evals)

### Create a CLI Codex can use

Ask Codex to create a composable CLI it can run from any folder, combine with repo scripts...EngineeringCode[Create a CLI Codex can useAsk Codex to create a composable CLI it can run from any folder, combine with repo scripts...EngineeringCode](/codex/use-cases/agent-friendly-clis)

### Follow a goal

Use `/goal` when a task needs Codex to keep working across turns toward a verifiable...EngineeringAutomation[Follow a goalUse `/goal` when a task needs Codex to keep working across turns toward a verifiable...EngineeringAutomation](/codex/use-cases/follow-goals)