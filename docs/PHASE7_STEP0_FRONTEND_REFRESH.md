# Phase 7 Step 0 Frontend Refresh

## Purpose

Before starting Phase 7 productization work, give MyAI a more polished and user-friendly interface baseline.

This is a bridge step between engineering capability and product experience. The goal is not to redesign every workflow at once, but to establish a stronger visual language and improve first impressions.

## Design Direction

MyAI should feel like a modern personal agent workbench:

- calm and capable
- inspectable rather than mysterious
- friendly without becoming toy-like
- dense enough for real work
- clearer about memory, knowledge, tasks, tools, and observability

## Step 0 MVP Scope

Implemented:

- Rebuilt login page as a two-column agent entry experience.
- Rebuilt register page with the same visual language.
- Added a CSS-only mascot illustration:
  - looks toward the user when username/email fields are focused
  - hides its eyes when password fields are focused
- Fixed login/register Chinese text display.
- Added responsive auth layout for mobile.
- Refreshed the main workbench visual skin without changing business behavior:
  - modern sidebar
  - softer workspace surface
  - upgraded cards and panels
  - clearer chat/message styling
  - upgraded inputs and action buttons

## Why CSS-Only Mascot

The mascot is built with HTML/CSS instead of external image assets.

Benefits:

- no dependency on external image downloads
- easy to animate through focus state
- consistent with local-first setup
- can be replaced later with generated or commissioned assets

## Deferred UI Work

The main workbench still needs deeper product design work screen by screen:

1. Chat page 2.0
   Add a stronger agent-style layout with conversation context, execution trace, memory/knowledge influence, and task handoff visible in a calmer way.

2. Memory page simplification
   Keep advanced governance metadata available, but make everyday memory control easier to scan.

3. Knowledge page workbench
   Make document QA, citations, summaries, maintenance, and ingestion state feel like a coherent document workspace.

4. Task page product polish
   Turn task runs, workflows, tool directory, and permission policy into a more guided operations surface.

5. Observability page refinement
   Add quality gate and maintenance report controls after Phase 6.7, then make health status easier to understand at a glance.

6. Settings and health unification
   Combine user settings, model settings, memory policy, connector status, eval gate status, and local runtime health.

## Productization Principle

Future UI work should make capabilities easier to trust and use, not only more visually impressive.

For MyAI, "advanced" should mean:

- users can see what happened
- users can correct or override behavior
- users can understand whether the system is healthy
- users can move between chat, memory, knowledge, tasks, and observability without feeling lost

## Recommended Next UI Increment

After Step 0, the best next UI target is the chat page.

Reason:

- Chat is the first daily-use surface.
- It is where memory, knowledge, tasks, tools, and trace all converge.
- Improving chat will make the agent capabilities feel more coherent immediately.
