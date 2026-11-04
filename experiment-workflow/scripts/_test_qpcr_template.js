/* Migration acceptance: execute the delivered professional skill, not copied formulas. */
const {spawnSync}=require('child_process');
const path=require('path');
const root=path.resolve(__dirname,'..','..');
const python=process.env.QPCR_PYTHON || (process.platform==='win32'?'py':'python3');
const args=process.platform==='win32' && !process.env.QPCR_PYTHON?['-3.9']:[];
const result=spawnSync(python,[...args,'-B','-m','unittest','discover','-s','sub_skill/cell-qpcr/tests','-v'],{cwd:root,stdio:'inherit'});
process.exit(result.status===null?1:result.status);
