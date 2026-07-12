# CODEWERK Product Roadmap

## Product Vision

CODEWERK is a programming and automation game in which the player grows from controlling one maintenance drone to designing an autonomous industrial production system. The pleasure comes from watching correct code operate visibly, identifying bottlenecks, and replacing repeated instructions with increasingly general solutions.

The game teaches normal Python concepts through useful factory problems. New progression should primarily unlock new decisions, information, and automation capabilities rather than percentage-only upgrades.

## Core Experience

The persistent game loop after the tutorial is:

1. Inspect up to eight customer requests.
2. Accept several orders with different products, payouts, quantities, and bonus deadlines.
3. Buy raw materials through Python.
4. Route the drone through player-placed machines.
5. Store finished products in the unlimited shipping warehouse.
6. Prioritize active orders through code.
7. Ship an order atomically when its complete quantity is available.
8. Reinvest earnings into machines, floor space, and new technology.

The factory, active orders, inventories, programs, and player-created modules persist. Contracts create goals, while the factory remains a sandbox between deliveries.

## Completed: Tutorial and Chapter 1

### Tutorial

- Eight progressive missions teach movement, inventory, loops, machines, conditions, coordinates, functions, and multi-file code.
- Tutorial mission `main.py` files remain separate.
- Shared helper modules persist across all tutorials and the main factory.

### Chapter 1: Contract Manufacturing

- Persistent empty `10 x 10` main factory after tutorial completion.
- Mouse-driven build mode with free placement, free relocation of empty machines, and 75 percent resale.
- Parallel requests and orders accessible through UI and Python.
- Code-only raw-material purchasing and queryable input/shipping inventories.
- Steel, copper, polymer, press, mill, wire drawing, injection molding, and assembly.
- Product chain culminates in an actuator.
- Completion target: 12 delivered orders including an actuator; factory expands to `12 x 12`.
- Soft economy: late delivery loses only its bonus and recovery prevents an irreparable dead end.

Chapter 1 is functionally implemented in version 0.2.0. Its prices, deadlines, quantities, unlock pacing, and recovery behavior remain balance targets rather than final values.

## Next: Chapter 2 — Quality and Energy

Goal: make robust production more valuable than merely working production.

Planned systems:

- Energy consumption per machine and a factory-wide power limit.
- Quality inspection station and explicit good/rejected product counts.
- Predictable defect conditions rather than unexplained random punishment.
- Machine temperature, wear, and preventative maintenance sensors.
- Batch-oriented machines that reward accumulation and scheduling.
- Contracts with maximum energy, minimum quality, or waste constraints.
- Recycling machine that converts rejected parts into partial raw-material recovery.
- Production statistics API for throughput, idle time, energy, and reject rate.

Design constraint: failures must be observable through documented sensors before they become costly. Chapter 2 must not introduce irreversible bankruptcy.

## Chapter 3 — Parallel Systems

Goal: move from route optimization to coordination.

Planned systems:

- Second programmable drone unlocked late in the chapter.
- One persistent entry file per drone, such as `main_drone_1.py` and `main_drone_2.py`.
- Shared helper modules across every drone.
- Visible collision and blocking rules with safe detection APIs.
- Shared task queue or message API using normal Python-friendly data structures.
- Charging stations and energy-aware route planning.
- Contracts that require concurrent production lines.

Multi-drone support should not appear earlier. The player must first understand one-drone logistics and contract prioritization.

## Chapter 4 — Flexible Production

Goal: automate not only production but factory configuration.

Planned systems:

- Tool changes and configurable machine recipes.
- Product variants with shared intermediate parts.
- Limited buffer capacity and deliberate warehouse allocation.
- Optional Python API for machine configuration and later factory rearrangement.
- Changing request mixes that reward reusable planning code.
- Larger hall sections unlocked as full-width factory expansions rather than isolated puzzle maps.

Direct mouse building remains available. Code-driven reconfiguration is an advanced capability, not a replacement for usable controls.

## Chapter 5 — Autonomous Factory

Goal: allow the player to build a system that operates profitably without manual intervention.

Planned systems:

- Automated request evaluation, acceptance, rejection, purchasing, production, and shipping.
- Long-running request streams with varied profitability and urgency.
- Optional efficiency rankings for ticks, transport, energy, waste, and code actions.
- Large multi-product capstone contracts.
- Endgame sandbox after the campaign, preserving the completed factory.

The campaign ending should demonstrate that the player's own abstractions, not a purchased automation button, created the autonomous factory.

## Content and UX Principles

- Introduce one major source of complexity at a time.
- First successful solutions may be inefficient; optimization remains optional unless a contract explicitly teaches it.
- Every API must have searchable in-game documentation, signatures, return values, failure conditions, and runnable examples.
- Every machine must document position or placement behavior, inputs, outputs, duration, and operating sequence.
- Errors must identify the correct project file and line whenever possible.
- Avoid mandatory waiting, hidden random failures, and upgrades that only multiply output numbers.
- Keep code-facing information as snapshots made of standard Python dictionaries, lists, tuples, strings, numbers, and booleans.

## Near-Term Backlog

1. Playtest Chapter 1 profitability, deadlines, request refill delay, and technology pacing.
2. Add a detailed request/order inspector without reducing the need for code-based prioritization.
3. Add production history and throughput statistics.
4. Improve first-entry guidance for the empty main factory and code-only purchasing.
5. Design and prototype Chapter 2 energy and quality data models behind deterministic tests.

