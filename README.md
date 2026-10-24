# Claude Code + MetaMask Agent Wallet

A setup for letting Claude Code move small amounts of crypto onchain, where the limits live in the wallet, not in the prompt.

Use small amounts. Agent Wallet only opened to the public in August 2026, so treat it as new software. Nothing here is financial advice.

## How it fits together

```
Claude Code ── runs ──> mm CLI ── asks ──> server wallet (keys in a TEE at MetaMask)
    ▲                                              │
    │ skill: which commands, when to ask           │ outside your policy?
    │                                              ▼
 your Mac                              approval in MetaMask Mobile on your phone
```

- **Terminal:** MetaMask's `mm` CLI. Do the setup yourself, by hand, so the agent never picks its own guardrails.
- **Claude Code:** MetaMask's `metamask-agent-wallet` skill tells it which `mm` commands to run and when to stop and ask. Keep it in its own folder, away from your other agents.
- **Wallet:** a server wallet. The keys sit in a trusted execution environment on MetaMask's side, not on your machine.
- **Guardrails:** Guard Mode plus a policy with a daily outflow cap and an address allowlist. Anything outside them pauses until you approve it on your phone. The agent can't get round that, because it's enforced by the wallet.
- **Gas:** on chains with relay support (Base is one), token transfers can pay their gas in the token itself, so the wallet can run on USDC alone with no ETH.

## Setup

**1. Requirements:** Node 22.18 or later, and MetaMask Mobile 7.82.0 or later on your phone.

**2. Check the package is MetaMask's, then install it.** Typosquatted wallet packages are a known attack.

```
npm view @metamask/agent-wallet maintainers
npm install -g @metamask/agent-wallet@latest
mm doctor
```

**3. Give it its own folder and add the skill there.** Pick `metamask-agent-wallet`, and choose project scope rather than global if it asks.

```
mkdir -p ~/agent-wallet && cd ~/agent-wallet
npx skills add MetaMask/agent-skills
```

**4. Sign in with MetaMask Mobile.**

```
mm login qr
```

Scan the QR code in the MetaMask app and approve. Why QR rather than Google or email: approvals then arrive in the app on your phone. With Google or email they arrive as email links, and if any of your agents can read your inbox, one agent could approve another's transaction.

Pick one sign-in method and stick to it. Google, email and QR each give you a **different wallet address**, even with the same email.

**5. Create the wallet in Guard Mode.**

```
mm init --wallet server-wallet --mode guard
mm wallet address
mm doctor
```

`mm doctor` should show `authenticated: true` and `initialized: true` before you go any further.

**6. Set your policy before you fund it.** See the next section.

**7. Fund it with a small amount, then test the whole loop** by sending a little back to your own main wallet and approving it on your phone:

```
mm wallet balance --chain-ids 8453
mm transfer --to <YOUR_MAIN_WALLET> --amount 1 --token USDC --chain-id 8453 --wait
mm tx history --limit 5
```

The transfer prints `AWAITING_MFA` while it waits for you. If no push notification arrives, check the notifications menu in MetaMask Mobile. If it hangs, don't run it again or you may send twice; check `mm wallet requests list` instead.

## Policy

Always start from the template: `mm wallet policy template`. Things that tripped me up:

- Allowlist entries are objects with `address` and `chain_id` (`0` means every chain), not bare addresses.
- In schema v1 you can't remove the default chains, so the cap and the allowlist are what protect you.
- Mine started with a $0 daily limit, which means every outflow needs your approval until you raise it.
- Tightening the policy applies at once. Loosening it (raising the cap, adding an address) needs approval on your phone.

Save this as `~/agent-wallet/policy.yaml` with your own values:

```yaml
schema_version: 1
wallet_address: "<AGENT_WALLET_ADDRESS>"
addresses:
  allowlist:
    - address: "<YOUR_MAIN_WALLET>"
      chain_id: 0
  blocklist: []
evm:
  allowed_chains:
    - 1
    - 10
    - 56
    - 137
    - 143
    - 999
    - 1329
    - 4326
    - 4663
    - 8453
    - 42161
    - 43114
    - 46630
    - 59144
    - 84532
    - 11155111
  outflow_limits_usd:
    rolling_24h: 10
```

Then apply and check it:

```
mm wallet policy set --policy "$(cat ~/agent-wallet/policy.yaml)"
mm wallet policy get
```

## House rules for the agent

Put these in `~/agent-wallet/CLAUDE.md`. The outflow cap doesn't count signatures such as Permit2, and a malicious permit is the classic way wallets get drained, so this closes the gap:

```
Never run mm wallet sign-typed-data or approve token allowances without asking me first.
Only send to allowlisted addresses.
Never change the trading mode or the wallet policy.
```

Then open Claude Code in that folder (`cd ~/agent-wallet && claude`) and ask it: "Show my wallet address and balance."

## My dashboard card

My personal dashboard, a private build of my open-source [HUD](https://github.com/markcfa/personal-hud), has an Agent Wallet card. A read-only script on my Mac runs the `mm` commands every 15 minutes, and the card shows:

- the USDC balance on Base
- anything waiting for my approval, highlighted, with a Telegram ping if it has been waiting more than 15 minutes
- today's spend against the daily cap (an estimate, as there's no CLI command for it yet)
- a red alarm if the wallet is ever switched out of Guard Mode or the cap is raised
- the last five transactions, with BaseScan links
- CLI health: signed in, initialised, and the skill version matching the CLI

Every `mm` command takes `--json`, which is what makes this easy:

```
mm wallet balance --chain-ids 8453 --json
mm wallet requests list --json
mm tx history --limit 5 --json
mm wallet trading-mode get --json
mm wallet policy get --json
mm doctor --json
```

[`examples/agentwallet_sync.py`](examples/agentwallet_sync.py) is a stripped-down version of my script to start from. It writes one JSON file holding the raw output plus a few alerts, and it never runs anything that moves money or changes the policy. Keep any script like this read-only, and keep its output file out of git, because it holds balances and addresses.

## Things worth knowing

- Keep the agent that holds this skill away from unattended jobs that read the open web. A poisoned page is a prompt-injection route; the policy limits the damage, but separation is cleaner.
- `mm wallet balance --address` only works for wallets on your Agent Wallet account, not for any address.
- Old wallets fill up with fake airdropped tokens using familiar names such as USDC. Always check the contract address before sending anything.
- Don't publish your wallet addresses anywhere they can be tied to your name, particularly if one resolves to an ENS name.

## MetaMask docs

- [Quickstart](https://docs.metamask.io/agent-wallet/quickstart/)
- [CLI setup](https://docs.metamask.io/agent-wallet/cli-setup/)
- [Trading modes](https://docs.metamask.io/agent-wallet/reference/trading-modes/)
- [Outflow policy](https://docs.metamask.io/agent-wallet/reference/outflow-policy/)
- [Commands reference](https://docs.metamask.io/agent-wallet/reference/commands/)
