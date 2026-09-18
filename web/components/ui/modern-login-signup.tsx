"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

import { CSSProperties, FormEvent, useEffect, useRef, useState } from "react";
import { ShieldAlert } from "lucide-react";

/**
 * Full-screen login splash.
 *
 * The animated dot field is a WebGL fragment shader rendered with Three.js,
 * loaded from a CDN at runtime (the original component deliberately avoids a
 * bundler import). Everything else is the auth card: username + password,
 * posted to the existing `/api/auth/login` route in `app/api/auth/login`.
 *
 * The social/sign-up chrome from the original design was dropped because this
 * app has a single configured credential and no sign-up flow (see
 * `lib/auth.ts`) — dead buttons are worse than fewer buttons.
 */

let threePromise: Promise<any> | null = null;

function loadThree(): Promise<any> {
  const w = window as any;
  if (w.THREE) return Promise.resolve(w.THREE);
  if (!threePromise) {
    threePromise = new Promise((resolve, reject) => {
      const existing = document.getElementById(
        "three-cdn",
      ) as HTMLScriptElement | null;
      const script = existing ?? document.createElement("script");
      script.id = "three-cdn";
      script.src =
        "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
      script.async = true;
      script.addEventListener("load", () => resolve((window as any).THREE));
      script.addEventListener("error", () => {
        threePromise = null;
        reject(new Error("Failed to load Three.js"));
      });
      if (!existing) document.head.appendChild(script);
    });
  }
  return threePromise;
}

function safeNext(value: string | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/upload";
  }
  return value;
}

export default function ModernLoginSignup({ next }: { next?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let active = true;
    let renderer: any;
    let geometry: any;
    let material: any;
    let animationId = 0;
    let handleResize: (() => void) | undefined;

    loadThree()
      .then((THREE) => {
        if (!active || !canvasRef.current) return;
        const canvas = canvasRef.current;

        renderer = new THREE.WebGLRenderer({
          canvas,
          alpha: true,
          antialias: false,
        });
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.setSize(window.innerWidth, window.innerHeight);

        const scene = new THREE.Scene();
        const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

        const uniforms = {
          u_time: { value: 0 },
          u_resolution: {
            value: new THREE.Vector2(window.innerWidth * 2, window.innerHeight * 2),
          },
          u_opacities: {
            value: [0.3, 0.3, 0.3, 0.5, 0.5, 0.5, 0.8, 0.8, 0.8, 1.0],
          },
          u_colors: {
            value: [
              new THREE.Vector3(1, 1, 1),
              new THREE.Vector3(1, 1, 1),
              new THREE.Vector3(1, 1, 1),
              new THREE.Vector3(1, 1, 1),
              new THREE.Vector3(1, 1, 1),
              new THREE.Vector3(1, 1, 1),
            ],
          },
          u_total_size: { value: 20.0 },
          u_dot_size: { value: 6.0 },
          u_reverse: { value: 0 },
        };

        material = new THREE.ShaderMaterial({
          vertexShader: `
            precision mediump float;
            uniform vec2 u_resolution;
            out vec2 fragCoord;
            void main() {
              gl_Position = vec4(position, 1.0);
              fragCoord = (position.xy + 1.0) * 0.5 * u_resolution;
              fragCoord.y = u_resolution.y - fragCoord.y;
            }
          `,
          fragmentShader: `
            precision mediump float;
            in vec2 fragCoord;

            uniform float u_time;
            uniform float u_opacities[10];
            uniform vec3 u_colors[6];
            uniform float u_total_size;
            uniform float u_dot_size;
            uniform vec2 u_resolution;
            uniform int u_reverse;

            out vec4 fragColor;

            float PHI = 1.61803398874989484820459;
            float random(vec2 xy) {
                return fract(tan(distance(xy * PHI, xy) * 0.5) * xy.x);
            }

            void main() {
                vec2 st = fragCoord.xy;
                st.x -= abs(floor((mod(u_resolution.x, u_total_size) - u_dot_size) * 0.5));
                st.y -= abs(floor((mod(u_resolution.y, u_total_size) - u_dot_size) * 0.5));

                float opacity = step(0.0, st.x) * step(0.0, st.y);

                vec2 st2 = vec2(int(st.x / u_total_size), int(st.y / u_total_size));

                float frequency = 5.0;
                float show_offset = random(st2);
                float rand = random(st2 * floor((u_time / frequency) + show_offset + frequency));
                opacity *= u_opacities[int(rand * 10.0)];
                opacity *= 1.0 - step(u_dot_size / u_total_size, fract(st.x / u_total_size));
                opacity *= 1.0 - step(u_dot_size / u_total_size, fract(st.y / u_total_size));

                vec3 color = u_colors[int(show_offset * 6.0)];

                float animation_speed_factor = 3.0;
                vec2 center_grid = u_resolution / 2.0 / u_total_size;
                float dist_from_center = distance(center_grid, st2);

                float timing_offset_intro = dist_from_center * 0.01 + (random(st2) * 0.15);

                float current_timing_offset = timing_offset_intro;
                opacity *= step(current_timing_offset, u_time * animation_speed_factor);
                opacity *= clamp((1.0 - step(current_timing_offset + 0.1, u_time * animation_speed_factor)) * 1.25, 1.0, 1.25);

                fragColor = vec4(color, opacity);
                fragColor.rgb *= fragColor.a;
            }
          `,
          uniforms,
          glslVersion: THREE.GLSL3,
          blending: THREE.CustomBlending,
          blendSrc: THREE.SrcAlphaFactor,
          blendDst: THREE.OneFactor,
          transparent: true,
        });

        geometry = new THREE.PlaneGeometry(2, 2);
        scene.add(new THREE.Mesh(geometry, material));

        const startTime = performance.now();
        const animate = () => {
          if (!active) return;
          animationId = requestAnimationFrame(animate);
          uniforms.u_time.value = (performance.now() - startTime) / 1000.0;
          renderer.render(scene, camera);
        };
        animate();

        handleResize = () => {
          renderer.setSize(window.innerWidth, window.innerHeight);
          uniforms.u_resolution.value.set(
            window.innerWidth * 2,
            window.innerHeight * 2,
          );
        };
        window.addEventListener("resize", handleResize);
      })
      .catch(() => {
        /* The dot field is decorative; the card still works without it. */
      });

    return () => {
      active = false;
      if (animationId) cancelAnimationFrame(animationId);
      if (handleResize) window.removeEventListener("resize", handleResize);
      if (renderer) renderer.dispose();
      if (geometry) geometry.dispose();
      if (material) material.dispose();
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as
          | { error?: string }
          | null;
        setError(data?.error ?? "Could not sign in.");
        return;
      }
      // Full-document navigation so the new session cookie is sent on a fresh
      // request and the middleware re-evaluates. An SPA push/refresh here can
      // resolve against a cached unauthenticated redirect and appear to no-op.
      window.location.assign(safeNext(next));
    } catch {
      setError("Could not sign in.");
    } finally {
      setPending(false);
    }
  }

  const input: CSSProperties = {
    width: "100%",
    padding: "0.65rem 0.85rem",
    borderRadius: 6,
    border: "1px solid #333",
    background: "#000",
    color: "#fff",
    fontSize: "0.875rem",
    outline: "none",
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        background: "#000",
        color: "#fff",
      }}
    >
      {/* WebGL dot canvas */}
      <canvas
        ref={canvasRef}
        aria-hidden
        style={{ position: "absolute", inset: 0, zIndex: 0 }}
      />

      {/* Vignette */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          zIndex: 1,
          background:
            "radial-gradient(circle at center,rgba(0,0,0,0.75) 0%,rgba(0,0,0,0) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Modal card */}
      <div
        style={{
          position: "relative",
          zIndex: 2,
          background: "#121212",
          borderRadius: 12,
          padding: "2rem",
          width: "100%",
          maxWidth: 400,
          boxShadow: "0 10px 40px rgba(0,0,0,0.8)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          border: "1px solid #222",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: 360,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
          }}
        >
          <div
            style={{
              background: "#111",
              width: 44,
              height: 44,
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "0.75rem",
              border: "1px solid #333",
            }}
          >
            <ShieldAlert size={20} aria-hidden />
          </div>
          <h1
            style={{
              fontSize: "1.35rem",
              fontWeight: 600,
              marginBottom: "0.25rem",
              letterSpacing: "-0.025em",
            }}
          >
            Sign in to Account
          </h1>
          <p
            style={{
              fontSize: "0.85rem",
              color: "#888",
              marginBottom: "0.85rem",
              lineHeight: 1.5,
            }}
          >
            Sign in to access the Security Anomaly Explorer.
          </p>

          <form
            onSubmit={onSubmit}
            style={{
              width: "100%",
              display: "flex",
              flexDirection: "column",
              gap: "0.65rem",
            }}
          >
            <input
              style={input}
              type="text"
              name="username"
              autoComplete="username"
              placeholder="Username"
              aria-label="Username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <input
              style={input}
              type="password"
              name="password"
              autoComplete="current-password"
              placeholder="Password"
              aria-label="Password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && (
              <p
                role="alert"
                style={{
                  fontSize: "0.8rem",
                  color: "#f87171",
                  textAlign: "left",
                }}
              >
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={pending}
              style={{
                width: "100%",
                padding: "0.65rem",
                borderRadius: 6,
                border: "none",
                background: "#ededed",
                color: "#000",
                fontWeight: 500,
                fontSize: "0.875rem",
                cursor: pending ? "default" : "pointer",
                opacity: pending ? 0.7 : 1,
              }}
            >
              {pending ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div
            style={{
              marginTop: "0.85rem",
              fontSize: "0.75rem",
              color: "#666",
              lineHeight: 1.5,
              textAlign: "center",
            }}
          >
            Authorized access only.
          </div>
        </div>
      </div>
    </div>
  );
}
