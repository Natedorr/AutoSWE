# failed_then_retry

Azure variant: work item in `autoswe:failed` state with `/retry` comment. Sync detects retry, resets attempt counter, and replays last substantive command (`/fix`). Final tag: `autoswe:done`.
