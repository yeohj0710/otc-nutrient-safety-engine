import { ImageResponse } from "next/og";

export const size = {
  width: 64,
  height: 64,
};

export const contentType = "image/png";

export default function Icon() {
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
          fontSize: 28,
          fontWeight: 700,
          borderRadius: 16,
          border: "2px solid rgba(28,25,23,0.08)",
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
