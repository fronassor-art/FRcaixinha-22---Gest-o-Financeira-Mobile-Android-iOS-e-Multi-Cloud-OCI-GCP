/* M40940 six-phase Master supermacropacote summary, no activation. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLaunchReadiness,parseSupermacroReadiness} from '../services/launchReadiness';

const phases=[
  ['P0','Arquitetura SQL e segregação Master','BLOCKED_SECURITY'],
  ['P1','Identidade, auditoria e RLS','BLOCKED_SECURITY'],
  ['P2','Staging, integração e CI','BLOCKED_EXTERNAL'],
  ['P3','Android release e UX','BLOCKED_EXTERNAL'],
  ['P4','Provedor e jurídico','BLOCKED_EXTERNAL'],
  ['P5','Termux e migração autorizada','BLOCKED_AUTHORIZATION'],
].map(([id,name,status])=>({id,name,status}));
const example={
  status:'BLOCKED',source:'SOURCE_ONLY_NOT_RUNTIME_ATTESTED',
  plan_available:true,total_tasks:34,pending_tasks:33,phases,
};
assert.equal(parseSupermacroReadiness(example).pending_tasks,33);
assert.equal(parseSupermacroReadiness(undefined).status,'BLOCKED');
assert.equal(parseSupermacroReadiness(undefined).plan_available,false);
for(const invalid of [
  {...example,status:'READY'},
  {...example,source:'LIVE_ATTESTED'},
  {...example,total_tasks:33,pending_tasks:0},
  {...example,total_tasks:34,pending_tasks:35},
  {...example,total_tasks:'34'},
  {...example,pending_tasks:'33'},
  {...example,total_tasks:null},
  {...example,pending_tasks:undefined},
  {...example,total_tasks:Number.NaN},
  {...example,pending_tasks:Number.POSITIVE_INFINITY},
  {...example,phases:phases.slice(0,5)},
  {...example,phases:[...phases.slice(0,5),{...phases[5],status:'APPROVED'}]},
  {...example,plan_available:false},
]){
  assert.throws(()=>parseSupermacroReadiness(invalid));
}
const source=readFileSync('src/components/LaunchReadinessPanel.tsx','utf8');
assert.match(source,/Supermacropacote — etapas e dependências/);
assert.match(source,/supermacropacote\.phases\.map/);
assert.match(source,/Nenhuma fase está homologada/);
assert.doesNotMatch(source,/triggerMigration\(|enablePix\(|enableProduction\(/);
console.log('M40940_MASTER_SUPERMACRO_PLAN_UI=PASS_NO_GO');
