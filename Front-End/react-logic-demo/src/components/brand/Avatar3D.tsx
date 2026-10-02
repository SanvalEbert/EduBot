/*
MELHORIA (Roteiro Cena 3) — Avatar 3D falante, 100% offline (Three.js puro).

Constrói dois personagens ("cientistas" estilizados) a partir de primitivas do
Three.js — SEM baixar nenhum arquivo e SEM depender de site externo (Ready Player
Me foi abandonada por estar bloqueada na rede do projeto). A BOCA anima enquanto
`speaking` é verdadeiro; o avatar também pisca e respira.

LIMITE CONHECIDO: a voz atual é o TTS do navegador (Web Speech API), que NÃO
expõe o áudio para análise. Por isso a boca faz uma oscilação suave enquanto fala
(não fonema-a-fonema). Lip-sync fonético real virá com a AWS Polly (visemas com
timing) — basta alimentar `mouthRef` com a timeline.

Estilo: low-poly/cartoon amigável. Não é foto-realista (isso exigiria um modelo
.glb externo); é reconhecível e nunca quebra a demo.
*/
import { Component, MutableRefObject, ReactNode, useEffect, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { AvatarPersona, AvatarVariant } from "./avatars";

// AV.3 (Plano 3) — lip-sync real: mapa VISEMA (Polly pt-BR) -> abertura da boca.
// Quando o `useSpeech` fornece a timeline de visemas do Polly (visemeRef), a boca
// segue os fonemas; sem timeline (Web Speech), cai na oscilação suave por `speaking`.
const VISEME_OPEN: Record<string, number> = {
  sil: 0, p: 0.05, f: 0.15, v: 0.15, k: 0.3, t: 0.25, d: 0.25, s: 0.2,
  S: 0.28, T: 0.2, r: 0.3, n: 0.2, l: 0.25,
  a: 0.9, e: 0.55, E: 0.68, i: 0.35, o: 0.72, O: 0.82, u: 0.42, "@": 0.5,
};
const visemeOpen = (v: string): number => (v in VISEME_OPEN ? VISEME_OPEN[v] : 0.4);

/* ------------------------------------------------------------------ */
/* Personagem procedural                                               */
/* ------------------------------------------------------------------ */

function Character({ persona, speaking, visemeRef }: {
  persona: AvatarPersona;
  speaking: boolean;
  visemeRef?: MutableRefObject<string>;
}) {
  const { palette, variant } = persona;
  const rootRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);
  const mouthRef = useRef<THREE.Mesh>(null);
  const eyeLRef = useRef<THREE.Mesh>(null);
  const eyeRRef = useRef<THREE.Mesh>(null);

  const mouthOpen = useRef(0);
  const blink = useRef(0);
  const nextBlink = useRef(1.5 + Math.random() * 2.5);
  // VI.2 (Plano 4): "reduzir movimento" desliga as animações IDLE (piscar, respirar,
  // micro-rotação da cabeça); o lip-sync da boca continua (é conteúdo, não decoração).
  const reducedMotion = useRef(
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
  // AUDITORIA P4: o valor inicial (acima) só é lido UMA VEZ no mount — se o aluno
  // muda a preferência do SO enquanto a persona 3D já está montada (dashboard/
  // companheiro ficam na tela por sessões longas), a animação ficaria presa no
  // estado antigo. O listener mantém a ref ao vivo (sem re-render: é lida dentro
  // de useFrame, por quadro).
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => { reducedMotion.current = mq.matches; };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const reduce = reducedMotion.current;

    // --- BOCA (abre/fecha enquanto fala) — conteúdo, mantém mesmo com reduced-motion ---
    let target = 0;
    const viseme = visemeRef?.current;
    if (viseme != null) {
      // Lip-sync guiado por visemas (Polly) OU pela alternância do Web Speech
      // fallback — em ambos o useSpeech mantém o visemeRef atualizado.
      target = visemeOpen(viseme);
    } else if (speaking) {
      // Sem visemeRef (uso legado do avatar): oscilação suave.
      const wave = 0.5 + 0.5 * Math.sin(t * 11);
      const flutter = 0.5 + 0.5 * Math.sin(t * 27 + 1.3);
      target = THREE.MathUtils.clamp(0.15 + 0.7 * wave * (0.6 + 0.4 * flutter), 0, 0.9);
    }
    mouthOpen.current = THREE.MathUtils.damp(mouthOpen.current, target, 16, delta);
    if (mouthRef.current) mouthRef.current.scale.y = 0.14 + mouthOpen.current;

    // --- PISCADA (decorativa) ---
    if (!reduce) {
      nextBlink.current -= delta;
      if (nextBlink.current <= 0) {
        blink.current = 1;
        nextBlink.current = 2.5 + Math.random() * 3.5;
      }
      blink.current = THREE.MathUtils.damp(blink.current, 0, 20, delta);
    }
    const eyeScaleY = 1 - blink.current * 0.9;
    if (eyeLRef.current) eyeLRef.current.scale.y = eyeScaleY;
    if (eyeRRef.current) eyeRRef.current.scale.y = eyeScaleY;

    // --- RESPIRAÇÃO / MICRO-MOVIMENTO (decorativo) ---
    if (reduce) {
      // Posição neutra (centro da oscilação) — evita o salto de -0.15 se ficasse no inicial.
      if (rootRef.current) rootRef.current.position.y = 0;
      if (headRef.current) { headRef.current.rotation.y = 0; headRef.current.rotation.x = 0; }
    } else {
      if (rootRef.current) rootRef.current.position.y = Math.sin(t * 1.6) * 0.02;
      if (headRef.current) {
        headRef.current.rotation.y = Math.sin(t * 0.5) * 0.12;
        headRef.current.rotation.x = Math.sin(t * 0.8) * 0.04;
      }
    }
  });

  const mat = (color: string, rough = 0.85) => (
    <meshStandardMaterial color={color} roughness={rough} metalness={0} />
  );

  return (
    <group ref={rootRef} position={[0, -0.15, 0]}>
      {/* Ombros / busto (roupa) */}
      <mesh position={[0, -1.35, 0]}>
        <cylinderGeometry args={[0.55, 1.15, 1.4, 32]} />
        {mat(palette.cloth)}
      </mesh>
      {/* Colarinho */}
      {variant === "einstein" ? (
        <mesh position={[0, -0.78, 0.35]} rotation={[0.35, 0, 0]}>
          <boxGeometry args={[0.7, 0.35, 0.1]} />
          {mat("#f4f4f6")}
        </mesh>
      ) : (
        <mesh position={[0, -0.7, 0.15]}>
          <cylinderGeometry args={[0.42, 0.5, 0.5, 24]} />
          {mat(palette.accent)}
        </mesh>
      )}

      {/* Pescoço */}
      <mesh position={[0, -0.55, 0]}>
        <cylinderGeometry args={[0.32, 0.36, 0.5, 24]} />
        {mat(palette.skin)}
      </mesh>

      {/* CABEÇA (com micro-rotação) */}
      <group ref={headRef} position={[0, 0.35, 0]}>
        <mesh scale={[0.92, 1.02, 0.9]}>
          <sphereGeometry args={[1, 48, 48]} />
          {mat(palette.skin)}
        </mesh>

        {/* Orelhas */}
        <mesh position={[-0.9, 0, 0]}>
          <sphereGeometry args={[0.17, 20, 20]} />
          {mat(palette.skin)}
        </mesh>
        <mesh position={[0.9, 0, 0]}>
          <sphereGeometry args={[0.17, 20, 20]} />
          {mat(palette.skin)}
        </mesh>

        {/* Olhos (brancos + pupila) — piscam via scale.y */}
        <mesh ref={eyeLRef} position={[-0.33, 0.2, 0.82]} scale={[1, 1, 0.5]}>
          <sphereGeometry args={[0.17, 24, 24]} />
          {mat("#ffffff", 0.4)}
        </mesh>
        <mesh ref={eyeRRef} position={[0.33, 0.2, 0.82]} scale={[1, 1, 0.5]}>
          <sphereGeometry args={[0.17, 24, 24]} />
          {mat("#ffffff", 0.4)}
        </mesh>
        <mesh position={[-0.33, 0.2, 0.94]}>
          <sphereGeometry args={[0.075, 16, 16]} />
          {mat("#2a2320", 0.3)}
        </mesh>
        <mesh position={[0.33, 0.2, 0.94]}>
          <sphereGeometry args={[0.075, 16, 16]} />
          {mat("#2a2320", 0.3)}
        </mesh>

        {/* Sobrancelhas */}
        <mesh position={[-0.33, 0.42, 0.86]} rotation={[0, 0, -0.08]}>
          <boxGeometry args={[0.3, 0.06, 0.08]} />
          {mat(palette.hair)}
        </mesh>
        <mesh position={[0.33, 0.42, 0.86]} rotation={[0, 0, 0.08]}>
          <boxGeometry args={[0.3, 0.06, 0.08]} />
          {mat(palette.hair)}
        </mesh>

        {/* Nariz */}
        <mesh position={[0, 0, 0.95]}>
          <sphereGeometry args={[0.13, 20, 20]} />
          {mat(palette.skin)}
        </mesh>

        {/* Boca: cavidade escura (abre) + lábios */}
        <mesh ref={mouthRef} position={[0, -0.4, 0.84]} scale={[1, 0.14, 1]}>
          <boxGeometry args={[0.4, 0.4, 0.14]} />
          {mat("#5a2b2b", 0.6)}
        </mesh>

        {/* Cabelo / traços por persona */}
        {variant === "einstein" ? <EinsteinHair palette={palette} /> : <CurieHair palette={palette} />}
      </group>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Cabelos / traços característicos                                     */
/* ------------------------------------------------------------------ */

function EinsteinHair({ palette }: { palette: AvatarPersona["palette"] }) {
  const hairMat = <meshStandardMaterial color={palette.hair} roughness={0.95} metalness={0} />;
  // Tufos "elétricos" nas laterais/atrás (topo mais ralo, como o Einstein).
  const tufts: [number, number, number, number][] = [
    [-0.85, 0.35, -0.15, 0.5],
    [0.85, 0.35, -0.15, 0.5],
    [-0.6, 0.85, -0.2, 0.42],
    [0.6, 0.85, -0.2, 0.42],
    [0, 0.9, -0.55, 0.5],
    [-0.95, 0.65, -0.25, 0.34],
    [0.95, 0.65, -0.25, 0.34],
    [-0.35, 1.02, -0.25, 0.3],
    [0.35, 1.02, -0.25, 0.3]
  ];
  return (
    <group>
      {tufts.map(([x, y, z, r], i) => (
        <mesh key={i} position={[x, y, z]}>
          <sphereGeometry args={[r, 16, 16]} />
          {hairMat}
        </mesh>
      ))}
      {/* Bigode farto */}
      <mesh position={[0, -0.26, 0.9]}>
        <boxGeometry args={[0.5, 0.14, 0.16]} />
        {hairMat}
      </mesh>
      {/* Óculos redondos */}
      <mesh position={[-0.33, 0.2, 0.98]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.22, 0.028, 12, 28]} />
        <meshStandardMaterial color="#2b2b33" roughness={0.4} metalness={0.2} />
      </mesh>
      <mesh position={[0.33, 0.2, 0.98]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.22, 0.028, 12, 28]} />
        <meshStandardMaterial color="#2b2b33" roughness={0.4} metalness={0.2} />
      </mesh>
      <mesh position={[0, 0.2, 0.99]}>
        <boxGeometry args={[0.22, 0.03, 0.03]} />
        <meshStandardMaterial color="#2b2b33" roughness={0.4} metalness={0.2} />
      </mesh>
    </group>
  );
}

function CurieHair({ palette }: { palette: AvatarPersona["palette"] }) {
  const hairMat = <meshStandardMaterial color={palette.hair} roughness={0.9} metalness={0} />;
  // Cabelo repartido/preso para trás, feito de esferas — nenhuma cruza a FRENTE
  // do rosto (z sempre recuado ou nas laterais), para não escurecer a face.
  const puffs: [number, number, number, number][] = [
    [0, 0.72, -0.1, 0.62], // topo (crown)
    [0, 0.5, -0.5, 0.7], // massa de trás
    [-0.55, 0.62, -0.25, 0.42], // topo-esquerda
    [0.55, 0.62, -0.25, 0.42], // topo-direita
    [-0.72, 0.15, -0.15, 0.45], // lateral esquerda
    [0.72, 0.15, -0.15, 0.45], // lateral direita
    [-0.4, 0.8, 0.12, 0.3], // franja emoldurando (alto, longe dos olhos)
    [0.4, 0.8, 0.12, 0.3]
  ];
  return (
    <group>
      {puffs.map(([x, y, z, r], i) => (
        <mesh key={i} position={[x, y, z]}>
          <sphereGeometry args={[r, 20, 20]} />
          {hairMat}
        </mesh>
      ))}
      {/* Coque atrás */}
      <mesh position={[0, 0.3, -0.95]}>
        <sphereGeometry args={[0.42, 24, 24]} />
        {hairMat}
      </mesh>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Canvas + fallback                                                   */
/* ------------------------------------------------------------------ */

class SceneErrorBoundary extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn("[Avatar3D] falha ao montar o avatar 3D — usando fallback 2D.", error);
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

interface Avatar3DProps {
  persona: AvatarPersona;
  speaking: boolean;
  visemeRef?: MutableRefObject<string>;
  width?: number;
  height?: number;
  onError?: () => void;
}

export function Avatar3D({ persona, speaking, visemeRef, width = 220, height = 280, onError }: Avatar3DProps) {
  return (
    <div style={{ width, height, borderRadius: 12, overflow: "hidden", background: persona.bg ?? "#eef0fb" }}>
      <SceneErrorBoundary onError={() => onError?.()}>
        <Canvas
          dpr={[1, 2]}
          camera={{ position: [0, -0.1, 6.4], fov: 30 }}
          gl={{ antialias: true }}
          onCreated={({ camera }) => camera.lookAt(0, -0.1, 0)}
        >
          <hemisphereLight intensity={1.15} groundColor={"#b9b9c9"} color={"#ffffff"} />
          <directionalLight position={[2, 3, 3]} intensity={1.3} />
          <directionalLight position={[-2, 1, 1.5]} intensity={0.5} color={"#cfd6ff"} />
          <Character persona={persona} speaking={speaking} visemeRef={visemeRef} />
        </Canvas>
      </SceneErrorBoundary>
    </div>
  );
}

// Referência de tipo para manter a assinatura estável entre variantes.
export type { AvatarVariant };
