# Mise launch film: brief, style guide and beat grid

**Film in one line:** a 20-second product film that shows an area manager's night going from scattered numbers to one screen that says what to do tomorrow.

**Made in code.** One HTML page (`film.html`) draws every frame from a single function `render(t)`. Playwright steps through the timeline at 30 fps and screenshots each frame; ffmpeg joins them with a soundtrack synthesized in Python (`score.py`). No video model, no stock footage. Every UI shot is a real screenshot of the Mise dashboard.

## Style guide

| Element | Rule |
| --- | --- |
| Palette | Paper `#f5f8ff`, ink `#0a1a3f`, brand blue `#1a56f0`, soft blue `#e8efff`, critical red `#e2394b`, good green `#0f9d58`. Nothing else. |
| Type | Plus Jakarta Sans for words (700 to 800 for headlines), Sora for numbers. Headlines 64 px, left-aligned on a 160 px margin. Never centred title cards. |
| Layout | Left third holds the caption; right two-thirds holds the product. |
| Container | One product container for the whole film. It never cuts: each state is the same element changing size, radius and content, with a 6 px blur swap. |
| Camera | Slow push-ins (max 1.18x) on the part of the screenshot the caption talks about. One move per shot. |
| Text in | Each line rises from a mask, 0.45 s, ease-out-expo, on a beat. |
| Text out | Lines lift 24 px and fade, 0.25 s, half a beat before the next shot. |
| Emphasis | One blue word or one red number per caption. A ring or band marks the exact cell the caption names. |
| Texture | Faint blue dot grid drifting 20 px over the film; 4% film grain. |
| Banned | Gradient title cards, glow, purple, emoji, centred stacks of text, more than one accent per frame, any number not in the dashboard. |

## Sound

120 BPM, one beat = 0.5 s, 40 beats. Synthesized in code: kick on every beat from beat 5, hats on off-beats, a soft pad from beat 10, a click on every cursor press, a whoosh on every container morph, a tick on every number change and a low thump on the logo. All events sit on the beat grid below.

## Beat grid

| Beat | Time (s) | Shot | Picture | Caption | Sound |
| --- | --- | --- | --- | --- | --- |
| 0 to 4 | 0.0 to 2.5 | 1. Scale | Paper and dot grid | "10 kitchens." "6 brands." "5 meal slots." "One area manager." one line per beat | Hats, tick per line |
| 5 to 9 | 2.5 to 5.0 | 2. Chaos | Six source chips fly in (Swiggy, Zomato, POS export, roster sheet, WhatsApp, stock register), then are pulled into one point | "Tomorrow's answers are scattered." then "Mise puts them on one screen." | Kick starts; whoosh at 4.5 s |
| 10 to 17 | 5.0 to 9.0 | 3. Overview | The point opens into the product container with the real overview; push in on the banner; cursor clicks the bell; the alerts panel replaces the view | "2,609 orders forecast for tomorrow." then "9 alerts. Every one has an owner." | Pad starts; click at 8.0 s |
| 18 to 24 | 9.0 to 12.5 | 4. Staffing | Container morphs to the kitchen speed chart; band on Whitefield | "Whitefield dinner is 2 cooks short." with 45% → 23% → 9% on beats | Whoosh; tick per number |
| 25 to 30 | 12.5 to 15.5 | 5. Complaints | Container morphs to the heat map; ring on HSR Layout × Missing | "22 missing-item complaints at HSR Layout." | Whoosh; ping on the ring |
| 31 to 35 | 15.5 to 18.0 | 6. Ask Mise | Container becomes the chat; the question types in, the answer streams | "Ask in plain words." | Whoosh; click on send |
| 36 to 39 | 18.0 to 20.0 | 7. Lockup | Container shrinks into the Mise mark; wordmark and line | "Mise. Kitchen ops control tower." | Thump on beat 37; pad rings out |

## Critique loop

After each render, a contact sheet of 12 frames is checked against this brief and scored 1 to 10 on: hierarchy, motion, sync, brand, legibility. Anything under 8 is fixed and re-rendered.
