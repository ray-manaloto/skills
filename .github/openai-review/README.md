# Manual OpenAI PR review

After merging to the default branch, create the GitHub Actions environment
`openai-pr-review`. Restrict deployments to the default **branch** only, add
no tag rules, and disable bypass where your plan allows. Add
`OPENAI_REVIEW_API_KEY` to that environment only. Do not add a repository-wide
secret. Anyone who can modify the trusted branch can ultimately change
workflows on that branch, so keep its protection and review policies in place.

In **Actions → OpenAI PR review → Run workflow**, leave the default branch
selected and enter an open PR number. Only GitHub file patches (with paths)
are sent. No PR checkout, PR code execution, comments, merge approval, or
automatic runs. A review appears in the run summary with the head it reviewed.
The advisory result does not replace any required review.

This makes one OpenAI Responses API request, with storage disabled in the
request. It does not verify API credit eligibility or balance and does not
guarantee a cost-free run. Review only material you are permitted to send.
The sensitive-content checks are a precaution, not a guarantee: don't review
patches containing secrets or restricted content. Oversized, unavailable,
or incomplete patches fail rather than being silently truncated.
