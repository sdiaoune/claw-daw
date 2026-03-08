import React from "react";
import {Composition} from "remotion";
import {ClawDawViral} from "./ClawDawViral.jsx";

export const RemotionRoot = () => {
  return (
    <Composition
      id="ClawDawViral"
      component={ClawDawViral}
      durationInFrames={540}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        audioSrc: "generated-media/clawdaw-viral-audio.mp3",
      }}
    />
  );
};
