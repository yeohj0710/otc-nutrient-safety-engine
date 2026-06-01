import { ImageResponse } from "next/og";

export const size = {
  width: 180,
  height: 180,
};

export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "linear-gradient(135deg, rgb(244, 241, 234) 0%, rgb(214, 228, 211) 100%)",
          color: "rgb(28, 25, 23)",
          fontSize: 76,
          fontWeight: 700,
          borderRadius: 40,
          border: "4px solid rgba(28,25,23,0.08)",
        }}
      >
        NS
      </div>
    ),
    {
      ...size,
    },
  );
}
