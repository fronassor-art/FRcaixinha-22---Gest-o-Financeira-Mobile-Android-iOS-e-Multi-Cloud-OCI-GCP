/** M40510 — login viewport math isolated from browser and Android APIs.
 * Android WebView may keep a taller layout viewport when its keyboard opens.
 * The login's scroll region must fit the VISUAL viewport, not its 100dvh CSS box.
 */
export function visibleLoginHeight(
  layoutAvailable:number,
  visualHeight:number,
  visualOffsetTop:number,
  elementTop:number,
):number{
  if(!Number.isFinite(layoutAvailable)||layoutAvailable<=0)return 1;
  const layout=Math.max(1,Math.floor(layoutAvailable));
  if(![visualHeight,visualOffsetTop,elementTop].every(Number.isFinite) ||
      visualHeight<=0)return layout;
  // Both visual viewport and element rectangles use WebView CSS px.
  const visualBottom=visualOffsetTop+visualHeight;
  const visible=Math.max(1,Math.floor(visualBottom-elementTop));
  return Math.max(1,Math.min(layout,visible));
}
/** Never restore an Android WebView scroll offset from the previous session. */
export function resetLoginScroll(node:Pick<HTMLElement,'scrollTop'|'scrollLeft'>):void{
  node.scrollTop=0;
  node.scrollLeft=0;
}
