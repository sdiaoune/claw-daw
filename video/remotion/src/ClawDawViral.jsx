import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const COLORS = {
  bg: "#08031b",
  bg2: "#150834",
  panel: "rgba(19, 11, 53, 0.84)",
  line: "rgba(255, 255, 255, 0.11)",
  cream: "#fff1e7",
  text: "#ffeef6",
  muted: "#d4c7ea",
  accent: "#ff6d57",
  accentSoft: "#ff96a2",
  pink: "#ff7bd4",
  sky: "#6ed8ff",
  gold: "#ffc66d",
};

const HERO_START = 0;
const HERO_DURATION = 120;
const PROMPT_START = 120;
const PROMPT_DURATION = 105;
const PROOF_START = 225;
const PROOF_DURATION = 150;
const CTA_START = 375;
const CTA_DURATION = 165;

const tags = ["offline", "scriptable", "deterministic"];
const artifactTags = ["audio", "MIDI", "JSON", "quality gated"];

const terminalLines = [
  "$ claw-daw quality out/2026-03-08_viral_edm_clean_v1.json --out 2026-03-08_viral_edm_clean_v2 --preset edm_streaming --section-gain",
  "quality: PASS preset=edm_streaming",
  "-> out/2026-03-08_viral_edm_clean_v2.mp3",
  "-> out/2026-03-08_viral_edm_clean_v2.mid",
  "-> out/2026-03-08_viral_edm_clean_v2.json",
];

const stars = [
  {left: "8%", top: "12%", size: 10, color: COLORS.sky, drift: 0.8},
  {left: "22%", top: "16%", size: 7, color: COLORS.pink, drift: 1.2},
  {left: "82%", top: "15%", size: 9, color: COLORS.gold, drift: 0.9},
  {left: "88%", top: "28%", size: 6, color: COLORS.accentSoft, drift: 1.4},
  {left: "14%", top: "61%", size: 7, color: COLORS.gold, drift: 1.1},
  {left: "80%", top: "72%", size: 8, color: COLORS.sky, drift: 1.3},
  {left: "24%", top: "84%", size: 6, color: COLORS.pink, drift: 1.0},
  {left: "88%", top: "87%", size: 10, color: COLORS.accentSoft, drift: 1.25},
];

const eqBars = [0.2, 0.42, 0.68, 0.84, 0.7, 0.5, 0.34, 0.24];

const sceneStyle = {
  display: "flex",
  flexDirection: "column",
  gap: 28,
  paddingTop: 220,
  height: "100%",
};

const FullScreen = ({children}) => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(circle at 16% 18%, rgba(255,109,87,0.18), transparent 20%), radial-gradient(circle at 84% 20%, rgba(110,216,255,0.18), transparent 24%), radial-gradient(circle at 52% 62%, rgba(255,123,212,0.14), transparent 26%), linear-gradient(180deg, #09031d 0%, #130833 50%, #070319 100%)",
      color: COLORS.text,
      fontFamily:
        'Inter, "SF Pro Display", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      overflow: "hidden",
    }}
  >
    {children}
  </AbsoluteFill>
);

const HeaderPill = ({text, dot = COLORS.accent}) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 12,
      padding: "16px 24px",
      borderRadius: 999,
      background: "rgba(20, 12, 57, 0.78)",
      border: `1px solid ${COLORS.line}`,
      color: COLORS.cream,
      fontSize: 24,
      letterSpacing: "0.1em",
      textTransform: "uppercase",
      fontWeight: 850,
      boxShadow: "0 20px 48px rgba(0, 0, 0, 0.18)",
    }}
  >
    <span
      style={{
        width: 12,
        height: 12,
        borderRadius: 999,
        background: dot,
        boxShadow: `0 0 16px ${dot}`,
      }}
    />
    <span>{text}</span>
  </div>
);

const Brand = ({frame}) => {
  const bob = Math.sin(frame / 16) * 5;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 18,
        padding: "18px 24px",
        borderRadius: 999,
        background: "rgba(20, 12, 57, 0.78)",
        border: `1px solid ${COLORS.line}`,
        boxShadow: "0 20px 48px rgba(0, 0, 0, 0.18)",
        transform: `translateY(${bob}px)`,
      }}
    >
      <div
        style={{
          width: 58,
          height: 58,
          borderRadius: 20,
          background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.pink}, ${COLORS.sky})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 33,
          fontWeight: 900,
          color: COLORS.cream,
          boxShadow: `0 0 24px ${COLORS.pink}44`,
        }}
      >
        C
      </div>
      <div style={{display: "flex", flexDirection: "column", gap: 4}}>
        <div style={{fontSize: 42, fontWeight: 950, lineHeight: 1}}>claw-daw</div>
        <div style={{fontSize: 22, fontWeight: 700, color: "#f3abc0"}}>cute claws, serious workflow</div>
      </div>
    </div>
  );
};

const Panel = ({children, style}) => {
  const frame = useCurrentFrame();
  const pulse = 0.92 + ((Math.sin(frame / 14) + 1) / 2) * 0.08;

  return (
    <div
      style={{
        position: "relative",
        background: "linear-gradient(180deg, rgba(28, 16, 72, 0.92), rgba(10, 8, 30, 0.95))",
        border: `2px solid ${COLORS.line}`,
        borderRadius: 36,
        padding: 34,
        boxShadow: `inset 0 1px 0 rgba(255,255,255,0.08), 0 24px 72px rgba(0,0,0,0.24), 0 0 ${26 * pulse}px rgba(255,123,212,0.13)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

const FloatingStars = ({frame}) => (
  <>
    {stars.map((star, index) => {
      const y = Math.sin(frame / 16 + index) * 10 * star.drift;
      const scale = 0.85 + ((Math.sin(frame / 12 + index) + 1) / 2) * 0.35;

      return (
        <div
          key={index}
          style={{
            position: "absolute",
            left: star.left,
            top: star.top,
            width: star.size * 2,
            height: star.size * 2,
            transform: `translateY(${y}px) scale(${scale}) rotate(${frame * 0.35 * star.drift}deg)`,
            opacity: 0.95,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(90deg, transparent 44%, ${star.color} 44%, ${star.color} 56%, transparent 56%), linear-gradient(180deg, transparent 44%, ${star.color} 44%, ${star.color} 56%, transparent 56%)`,
              borderRadius: 999,
              filter: `drop-shadow(0 0 12px ${star.color})`,
            }}
          />
        </div>
      );
    })}
  </>
);

const SceneCard = ({children}) => (
  <div
    style={{
      maxWidth: 960,
      width: "100%",
    }}
  >
    {children}
  </div>
);

const SectionKicker = ({children}) => (
  <div
    style={{
      color: "#f7d3ff",
      fontSize: 22,
      textTransform: "uppercase",
      letterSpacing: "0.14em",
      fontWeight: 850,
    }}
  >
    {children}
  </div>
);

const Equalizer = () => {
  const frame = useCurrentFrame();

  return (
    <div style={{display: "flex", alignItems: "flex-end", gap: 12, height: 96}}>
      {eqBars.map((base, index) => {
        const pulse = (Math.sin(frame / 3.2 + index * 0.8) + 1) / 2;
        const height = 28 + base * 42 + pulse * 18;

        return (
          <div
            key={index}
            style={{
              width: 32,
              height,
              borderRadius: 999,
              background: `linear-gradient(180deg, ${COLORS.accent}, ${COLORS.sky})`,
              boxShadow: `0 0 20px ${index % 2 === 0 ? COLORS.accentSoft : COLORS.sky}44`,
            }}
          />
        );
      })}
    </div>
  );
};

const HeroScene = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = spring({fps, frame, config: {damping: 18, stiffness: 120}});
  const rise = interpolate(intro, [0, 1], [46, 0]);
  const opacity = interpolate(intro, [0, 1], [0, 1]);

  return (
    <div style={{...sceneStyle, opacity, transform: `translateY(${rise}px)`}}>
      <SceneCard>
        <div style={{display: "flex", gap: 12, flexWrap: "wrap"}}>
          {tags.map((tag, index) => (
            <HeaderPill
              key={tag}
              text={tag}
              dot={index === 0 ? COLORS.accent : index === 1 ? COLORS.gold : COLORS.sky}
            />
          ))}
        </div>
      </SceneCard>

      <SceneCard>
        <div
          style={{
            fontSize: 96,
            lineHeight: 0.92,
            letterSpacing: "-0.06em",
            fontWeight: 950,
            color: COLORS.cream,
            textShadow:
              "0 0 26px rgba(255,123,212,0.18), 0 0 42px rgba(110,216,255,0.14), 0 8px 0 rgba(8,5,26,0.55)",
          }}
        >
          The CLI music workstation for humans and AI agents.
        </div>
      </SceneCard>

      <SceneCard>
        <div
          style={{
            maxWidth: 840,
            fontSize: 38,
            lineHeight: 1.35,
            color: COLORS.muted,
          }}
        >
          Local renders. Real files. Same seed, same result. This soundtrack came out of claw-daw and was exported with the deterministic quality workflow.
        </div>
      </SceneCard>

      <SceneCard>
        <Panel style={{display: "flex", alignItems: "center", justifyContent: "space-between", gap: 30}}>
          <div style={{display: "flex", flexDirection: "column", gap: 10}}>
            <SectionKicker>now playing</SectionKicker>
            <div style={{fontSize: 48, fontWeight: 900, lineHeight: 1, color: COLORS.cream}}>
              Viral EDM clean v2
            </div>
            <div style={{fontSize: 28, lineHeight: 1.35, color: COLORS.muted, maxWidth: 500}}>
              Cleaner pad layer, gated master, and a tighter vertical cut built for X.
            </div>
          </div>
          <Equalizer />
        </Panel>
      </SceneCard>
    </div>
  );
};

const PromptScene = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = spring({fps, frame, config: {damping: 18, stiffness: 110}});

  return (
    <div
      style={{
        ...sceneStyle,
        opacity: interpolate(intro, [0, 1], [0, 1]),
        transform: `translateY(${interpolate(intro, [0, 1], [34, 0])}px)`,
      }}
    >
      <SceneCard>
        <Panel>
          <SectionKicker>prompt used for this soundtrack</SectionKicker>
          <div
            style={{
              marginTop: 18,
              fontSize: 52,
              lineHeight: 1.28,
              color: COLORS.cream,
              fontWeight: 780,
            }}
          >
            "Make me a melodic club record that feels expensive, euphoric, and huge in the first 15 seconds."
          </div>
          <div
            style={{
              marginTop: 22,
              fontSize: 30,
              lineHeight: 1.45,
              color: COLORS.muted,
            }}
          >
            One prompt, one deterministic render path, then a proper quality-gated export for the final soundtrack.
          </div>
        </Panel>
      </SceneCard>
    </div>
  );
};

const TerminalScene = () => {
  const frame = useCurrentFrame();

  return (
    <div style={sceneStyle}>
      <SceneCard>
        <Panel style={{paddingTop: 0, overflow: "hidden"}}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "18px 22px",
              borderBottom: `1px solid ${COLORS.line}`,
              textTransform: "uppercase",
              letterSpacing: "0.12em",
              fontSize: 20,
              fontWeight: 850,
              color: COLORS.cream,
              background: "rgba(255,255,255,0.03)",
            }}
          >
            <span style={{width: 12, height: 12, borderRadius: 999, background: COLORS.accent}} />
            <span style={{width: 12, height: 12, borderRadius: 999, background: COLORS.gold}} />
            <span style={{width: 12, height: 12, borderRadius: 999, background: COLORS.sky}} />
            local render proof
          </div>

          <div style={{padding: 28, display: "flex", flexDirection: "column", gap: 14}}>
            {terminalLines.map((line, index) => {
              const lineStart = index * 12;
              const lineIn = spring({
                fps: 30,
                frame: frame - lineStart,
                config: {damping: 18, stiffness: 120},
              });
              const opacity = interpolate(lineIn, [0, 1], [0, 1]);
              const y = interpolate(lineIn, [0, 1], [18, 0]);
              const isOutput = line.startsWith("->");
              const isStatus = line.startsWith("quality:");

              return (
                <div
                  key={line}
                  style={{
                    fontFamily:
                      'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                    fontSize: 23,
                    lineHeight: 1.45,
                    opacity,
                    transform: `translateY(${y}px)`,
                    color: isOutput ? COLORS.sky : isStatus ? COLORS.gold : COLORS.cream,
                    textShadow: isOutput ? `0 0 16px ${COLORS.sky}2f` : "none",
                  }}
                >
                  {line}
                </div>
              );
            })}
          </div>
        </Panel>
      </SceneCard>

      <SceneCard>
        <div style={{display: "flex", gap: 14, flexWrap: "wrap"}}>
          {artifactTags.map((tag, index) => (
            <HeaderPill
              key={tag}
              text={tag}
              dot={
                index === 0
                  ? COLORS.accent
                  : index === 1
                    ? COLORS.sky
                    : index === 2
                      ? COLORS.gold
                      : COLORS.pink
              }
            />
          ))}
        </div>
      </SceneCard>

      <SceneCard>
        <div
          style={{
            maxWidth: 880,
            fontSize: 34,
            lineHeight: 1.42,
            color: COLORS.muted,
          }}
        >
          claw-daw does not stop at a black-box MP3. You keep the audio, the MIDI, and the project JSON so both humans and agents can iterate on the result.
        </div>
      </SceneCard>
    </div>
  );
};

const CtaScene = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = spring({fps, frame, config: {damping: 17, stiffness: 100}});
  const opacity = interpolate(intro, [0, 1], [0, 1]);
  const y = interpolate(intro, [0, 1], [34, 0]);

  return (
    <div style={{...sceneStyle, opacity, transform: `translateY(${y}px)`}}>
      <SceneCard>
        <Panel>
          <SectionKicker>build with me</SectionKicker>
          <div
            style={{
              marginTop: 16,
              fontSize: 86,
              lineHeight: 0.94,
              letterSpacing: "-0.055em",
              fontWeight: 950,
              color: COLORS.cream,
            }}
          >
            Reply with a vibe.
            <br />
            I will turn it into a track.
          </div>

          <div
            style={{
              marginTop: 22,
              fontSize: 32,
              lineHeight: 1.42,
              color: COLORS.muted,
              maxWidth: 760,
            }}
          >
            Give me a scene, genre, or game moment. I will prompt claw-daw, render it locally, and ship the audio, MIDI, and JSON artifacts.
          </div>

          <div style={{marginTop: 24, display: "flex", gap: 16, flexWrap: "wrap"}}>
            <div
              style={{
                padding: "18px 28px",
                borderRadius: 999,
                background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.pink})`,
                color: COLORS.cream,
                fontSize: 28,
                fontWeight: 900,
                boxShadow: `0 0 24px ${COLORS.pink}33`,
              }}
            >
              clawdaw.com
            </div>
            <div
              style={{
                padding: "18px 28px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.04)",
                border: `1px solid ${COLORS.line}`,
                color: COLORS.cream,
                fontSize: 26,
                fontWeight: 800,
              }}
            >
              github.com/sdiaoune/claw-daw
            </div>
          </div>
        </Panel>
      </SceneCard>
    </div>
  );
};

export const ClawDawViral = ({audioSrc}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const progress = frame / durationInFrames;
  const progressWidth = `${Math.max(0, Math.min(100, progress * 100))}%`;

  return (
    <FullScreen>
      <Audio src={staticFile(audioSrc)} />
      <FloatingStars frame={frame} />

      <div
        style={{
          position: "absolute",
          inset: 0,
          padding: "58px 54px 54px",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 16,
          }}
        >
          <Brand frame={frame} />
          <HeaderPill text="music for humans + agents" dot={COLORS.sky} />
        </div>

        <Sequence from={HERO_START} durationInFrames={HERO_DURATION}>
          <HeroScene />
        </Sequence>

        <Sequence from={PROMPT_START} durationInFrames={PROMPT_DURATION}>
          <PromptScene />
        </Sequence>

        <Sequence from={PROOF_START} durationInFrames={PROOF_DURATION}>
          <TerminalScene />
        </Sequence>

        <Sequence from={CTA_START} durationInFrames={CTA_DURATION}>
          <CtaScene />
        </Sequence>

        <div style={{marginTop: "auto", paddingTop: 24}}>
          <div
            style={{
              height: 10,
              width: "100%",
              borderRadius: 999,
              background: "rgba(255,255,255,0.08)",
              border: `1px solid ${COLORS.line}`,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: progressWidth,
                borderRadius: 999,
                background: `linear-gradient(90deg, ${COLORS.accent}, ${COLORS.pink}, ${COLORS.sky})`,
                boxShadow: `0 0 18px ${COLORS.sky}55`,
              }}
            />
          </div>
        </div>
      </div>
    </FullScreen>
  );
};
