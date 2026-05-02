/// <reference types="nativewind/types" />

/** Explicit NativeWind type declaration for Tailwind className props. */
declare module "nativewind/types" {
  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  interface CustomClassName {}
}

declare module "*.png" {
  const value: number;
  export default value;
}
declare module "*.jpg" {
  const value: number;
  export default value;
}
