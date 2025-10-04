import React, { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, useGLTF, Environment } from "@react-three/drei";

function TableTennisModel(props) {
  const { scene } = useGLTF("/models/low_poly_table_tennis/scene.gltf"); 
  return <primitive object={scene} {...props} />;
}

export default function TableTennisScene() {
  return (
    <Canvas
      camera={{ position: [0, 3, 5], fov: 45 }} // pull back and higher
      style={{ width: "100%", height: "500px" }}
    >
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 10, 5]} intensity={0.5} />

      {/* OrbitControls */}
      <OrbitControls
        enablePan={false}             // no panning
        enableZoom={false}            // fix zoom
        minPolarAngle={Math.PI / 4}   // min vertical angle (up-down)
        maxPolarAngle={Math.PI / 4}   // max vertical angle = min => fixed vertical
        minAzimuthAngle={-Math.PI / 2} // left-right rotation limits
        maxAzimuthAngle={Math.PI / 2}  // 180° rotation range
      />

      {/* Load model */}
      <Suspense fallback={null}>
        <TableTennisModel 
          position={[0, 0, 0]} 
          scale={[0.3, 0.3, 0.3]} // reduce scale to see full table
        />
      </Suspense>

      {/* Optional environment */}
      <Environment preset="studio" />
    </Canvas>
  );
}
