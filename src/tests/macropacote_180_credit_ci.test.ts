/* Macropacote 180: 20 testes adversariais sintéticos de simulação. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseLoanSimulation} from '../services/loanSimulationBoundary';
const amort=[67.19,80.63,96.75,116.10,139.33];
const interest=[100,86.56,70.44,51.09,27.87];
const opening=[500,432.81,352.18,255.43,139.33];
const closing=[432.81,352.18,255.43,139.33,0];
const schedule=amort.map((part,i)=>({
 installment_number:i+1,due_date:'2027-'+String(i+1).padStart(2,'0')+'-10',
 opening_balance:opening[i].toFixed(2),interest_portion:interest[i].toFixed(2),
 amortization_portion:part.toFixed(2),
 monthly_payment:(part+interest[i]).toFixed(2),
 closing_balance:closing[i].toFixed(2),is_cents_adjusted:i===4
}));
const data={principal:'500.00',monthly_rate:'0.20',term_months:5,
 uniform_payment:'167.19',last_payment:'167.20',total_interest:'335.96',
 total_payable:'835.96',is_irregular_first_period:false,
 first_period_days:null,effective_first_rate:'0.20000000',schedule};
const req={principal:500,term_months:5};
let checks=0;const check=(f:()=>void)=>{f();checks++};
const reject=(x:unknown)=>assert.throws(()=>parseLoanSimulation(x,req));
check(()=>assert.equal(parseLoanSimulation(data,req).total_payable,835.96));
check(()=>assert.equal(parseLoanSimulation(data,req).schedule[4].closing_balance,0));
check(()=>reject({...data,cpf:'hidden'}));
check(()=>reject({...data,random_private_payload:'hidden'}));
check(()=>reject({...data,schedule:schedule.map((r,i)=>i===0?{...r,extra:'secret'}:r)}));
check(()=>reject({...data,is_irregular_first_period:true}));
check(()=>reject({...data,first_period_days:29}));
check(()=>reject({...data,first_period_days:30,effective_first_rate:'0.15'}));
check(()=>reject({...data,effective_first_rate:'0.19'}));
check(()=>reject({...data,principal:'500.01'}));
check(()=>reject({...data,total_payable:'835.95'}));
check(()=>reject({...data,total_interest:'335.95'}));
check(()=>reject({...data,monthly_rate:'NaN'}));
check(()=>reject({...data,term_months:6}));
check(()=>reject({...data,schedule:[]}));
check(()=>reject({...data,schedule:schedule.map((r,i)=>i===2?{...r,closing_balance:'0'}:r)}));
check(()=>reject({...data,schedule:schedule.map((r,i)=>i===1?{...r,due_date:'2027-04-10'}:r)}));
check(()=>reject({...data,schedule:schedule.map((r,i)=>i===1?{...r,installment_number:1}:r)}));
check(()=>reject({...data,schedule:schedule.map((r,i)=>i===1?{...r,interest_portion:'90.00'}:r)}));
check(()=>reject({...data,schedule:schedule.map((r,i)=>i===4?{...r,monthly_payment:'167.21'}:r)}));
assert.equal(checks,20);
const ui=readFileSync('src/components/ServerLoansView.tsx','utf8');
assert.match(ui,/authService\.captureSession\(\)/);
assert.match(ui,/authService\.isSessionSnapshotCurrent\(snapshot\)/);
assert.match(ui,/requestId !== simulationRequestId\.current/);
assert.match(ui,/Não equivale a oferta, aprovação ou desembolso/);
assert.doesNotMatch(ui,/requestLoan\(|approveLoan\(|disburseLoan\(|repayLoan\(/);
const backend=readFileSync('backend/app/routers/loans.py','utf8');
assert.match(backend,/policy_limit = policy\["max_installments"\]/);
assert.match(backend,/P > Decimal\('50000\.00'\)/);
console.log('MACROPACOTE_180_PRICE_CLIENT_CI=PASS');
