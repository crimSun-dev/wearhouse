# Release evidence: avatar frame rate (RQ4)

Change `add-wearhouse-frontend`, task 5.3. This file records what the avatar frame-rate route measured, on which device, and what has not been measured yet.

## How it is measured

`#/dev/avatar-fps` (live: https://crimsun-dev.github.io/wearhouse/app/#/dev/avatar-fps) loads the 3D avatar wearing a full look: every slot, with two wrist, two ring and three accessory pieces. It rotates the look for 60 seconds, skips the first 0.5 s (shader compile), and reports the median frame rate over all frames together with the browser, CPU threads, memory and the WebGL renderer string.

In the app, the fitting room watches the first 3 seconds of 3D frames. If the median is below 30 fps, it switches that device to the 2D view, remembers the choice on the device, and says so ("this device rendered 3D below 30 fps"). The end-to-end test `e2e/avatar.e2e.spec.ts` ("Low frame rate") checks that switch by making each animation frame take about 45 ms of main-thread work.

## Results

| Date | Device | Renderer | Median FPS | Frames | Fallback |
|---|---|---|---|---|---|
| 2026-11-26 | Desktop: MSI MS-7D36, AMD Ryzen 9 5950X (32 threads), 64 GB RAM, NVIDIA GeForce RTX 3090; Chrome 159 (headless), 1280×900 | ANGLE, Direct3D 11, RTX 3090 (hardware) | **59.9** | 3567 | No |
| 2026-11-26 | Same desktop, GPU disabled | ANGLE, SwiftShader (software rendering on the CPU) | **59.9** | 3571 | No |
| — | Laptop | — | **Not measured** | — | — |
| — | Mid-range phone | — | **Not measured** | — | — |

Both desktop runs hit the 60 Hz frame cap, so they show that the placeholder models are light, not how much headroom there is. The software run is a rough lower bound for machines without a usable GPU, but this CPU is much faster than a typical laptop's, so it does not stand in for one.

## Still to measure

Open `#/dev/avatar-fps` on a laptop and on a mid-range Android phone (for example, a Samsung Galaxy A-series), press **Start 60 s run**, and add a row with the device name, the renderer string the page prints, the median and the frame count. If a device reports below 30 fps, also confirm that the fitting room on that device shows the 2D view with the low-frame-rate notice.
