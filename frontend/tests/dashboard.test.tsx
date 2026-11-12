import {describe,it,expect,vi,beforeEach} from 'vitest';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import Dashboard,{FindingCard} from '@/components/dashboard';
import {api,type Analysis,type Draft} from '@/lib/api';
vi.mock('@/lib/api',async()=>{const actual=await vi.importActual<typeof import('@/lib/api')>('@/lib/api');return {...actual,api:{...actual.api,me:vi.fn(),overview:vi.fn(),integrations:vi.fn(),transactions:vi.fn(),transaction:vi.fn(),documents:vi.fn(),history:vi.fn(),analysis:vi.fn(),details:vi.fn(),audit:vi.fn(),draft:vi.fn(),saveDraft:vi.fn(),approve:vi.fn()}}});
const analysis:Analysis={analysis_id:'analysis_1',transaction_id:'txn_1',status:'completed',findings:[],draft_response:'Source-backed synthetic draft.',merchant_approval_required:true};
const draft:Draft={analysis_id:'analysis_1',text:analysis.draft_response!,version:1,status:'draft',warnings:[],approved_by:null,approved_at:null};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.me).mockResolvedValue({email:'test@example.test',merchant_name:'Test Merchant',mode:'persistent',csrf_token:'synthetic-csrf'});vi.mocked(api.overview).mockResolvedValue({total_transactions:1,analyzed_transactions:1,open_cases:0,awaiting_review:1,evidence_issues:0,analyses:[analysis],activity:[],mode:'persistent'});vi.mocked(api.integrations).mockResolvedValue({mode:'persistent',persistence:'postgresql',ocr:'unavailable',paypal:'not-configured',paypal_verified:false,analysis_engine:'deterministic-local-v1',limitations:[]});const transaction={id:'txn_1',paypal_transaction_id:'DEMO-1001',amount:'150.00',currency:'USD',status:'COMPLETED',transaction_date:'2026-10-15T10:30:00Z',evidence_count:0};vi.mocked(api.transaction).mockResolvedValue(transaction);vi.mocked(api.transactions).mockResolvedValue({items:[transaction],total:1,page:1,page_size:10,origins:{txn_1:'synthetic'}});vi.mocked(api.documents).mockResolvedValue([]);vi.mocked(api.history).mockResolvedValue([analysis]);vi.mocked(api.analysis).mockResolvedValue(analysis);vi.mocked(api.details).mockResolvedValue({analysis_id:'analysis_1',engine:'ai_engine_v1',failure_code:null,result:null});vi.mocked(api.audit).mockResolvedValue({events:[],revisions:[draft]});vi.mocked(api.draft).mockResolvedValue(draft)});
describe('Merchant review',()=>{
 it('links findings to exact document IDs without inventing absent sources',()=>{const open=vi.fn();render(<FindingCard finding={{id:'f1',issue_type:'amount_mismatch',severity:'high',explanation:'Amounts differ.',recommendation:'Review invoice.',source_ids:['doc_real_1']}} onSource={open}/>);fireEvent.click(screen.getByRole('button'));expect(open).toHaveBeenCalledWith('doc_real_1');expect(screen.getByText('Amounts differ.')).toBeInTheDocument()});
 it('does not invent a source for missing evidence',()=>{render(<FindingCard finding={{id:'f2',issue_type:'missing_delivery_proof',severity:'high',explanation:'No delivery evidence.',recommendation:'Upload proof.',source_ids:[]}} onSource={vi.fn()}/>);expect(screen.queryByRole('button')).toBeNull();expect(screen.getByText(/no source document supplied/)).toBeInTheDocument()});
 it('saves edits before approval and requires explicit human review',async()=>{const edited={...draft,text:'Reviewed synthetic text.',version:2,warnings:['manual_edits_not_source_validated']};vi.mocked(api.saveDraft).mockResolvedValue(edited);vi.mocked(api.approve).mockResolvedValue({...edited,version:3,status:'approved',approved_by:'test',approved_at:'2026-10-22T00:00:00Z'});render(<Dashboard initialTransaction="txn_1"/>);fireEvent.change(await screen.findByLabelText('Select analysis run'),{target:{value:'analysis_1'}});const editor=await screen.findByLabelText('Draft response');fireEvent.change(editor,{target:{value:edited.text}});expect(screen.getByRole('button',{name:'Approve draft'})).toBeDisabled();fireEvent.click(screen.getByRole('button',{name:'Save draft'}));await waitFor(()=>expect(api.saveDraft).toHaveBeenCalledWith(draft,edited.text));await waitFor(()=>expect(screen.getByRole('button',{name:'Approve draft'})).not.toBeDisabled());fireEvent.click(screen.getByRole('button',{name:'Approve draft'}));expect(screen.getByRole('button',{name:'Record approval'})).toBeDisabled();fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByRole('button',{name:'Record approval'}));await waitFor(()=>expect(api.approve).toHaveBeenCalledWith(edited));expect(await screen.findByText('Merchant approval recorded. Nothing was submitted.')).toBeInTheDocument()});
 it('shows connection errors rather than an invented dashboard',async()=>{vi.mocked(api.me).mockRejectedValue(new Error('Backend unavailable.'));render(<Dashboard/>);expect(await screen.findByRole('alert')).toHaveTextContent('Backend unavailable.');expect(screen.getByRole('button',{name:'Retry connection'})).toBeInTheDocument()});
});

it('returns to login and removes merchant content when the session expires',async()=>{
 render(<Dashboard/>);
 await screen.findByText('Your evidence, in focus.');
 act(()=>window.dispatchEvent(new Event('proofpay:session-expired')));
 expect(await screen.findByRole('button',{name:'Sign in'})).toBeInTheDocument();
 expect(screen.queryByText('Test Merchant')).not.toBeInTheDocument();
 expect(screen.getByRole('alert')).toHaveTextContent('session expired');
});

it('offers registration and returns to sign in after account creation',async()=>{
 const {ApiError}=await import('@/lib/api');
 vi.mocked(api.me).mockRejectedValue(new ApiError(401,'AUTH_REQUIRED'));
 const register=vi.spyOn(api,'register').mockResolvedValue({status:'created'});
 render(<Dashboard/>);
 fireEvent.click(await screen.findByRole('button',{name:'Create an account'}));
 fireEvent.change(screen.getByLabelText('Merchant name'),{target:{value:'New Store'}});
 fireEvent.change(screen.getByLabelText('Email address'),{target:{value:'new@example.test'}});
 fireEvent.change(screen.getByLabelText('Password',{exact:true}),{target:{value:'Synthetic-password-42'}});
 fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'Mismatch'}});
 fireEvent.click(screen.getByRole('button',{name:'Create account'}));
 expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match');
 expect(register).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'Synthetic-password-42'}});
 fireEvent.click(screen.getByRole('button',{name:'Create account'}));
 expect(await screen.findByRole('status')).toHaveTextContent('Account created');
 expect(register).toHaveBeenCalledWith('New Store','new@example.test','Synthetic-password-42');
 expect(screen.getByRole('button',{name:'Sign in'})).toBeInTheDocument();register.mockRestore();
});

it('opens file selection from an empty account and clears the analyzed filter',async()=>{
 const transaction={id:'txn_test',paypal_transaction_id:'PROOFPAY-TEST',amount:'150.00',currency:'USD',status:'COMPLETED',transaction_date:'2026-11-12T10:00:00Z',evidence_count:0};
 vi.mocked(api.overview).mockResolvedValue({total_transactions:0,analyzed_transactions:0,open_cases:0,awaiting_review:0,evidence_issues:0,analyses:[],activity:[],mode:'persistent'});
 vi.mocked(api.transactions).mockResolvedValue({items:[],total:0,page:1,page_size:10,origins:{}});
 vi.mocked(api.transaction).mockResolvedValue(transaction);
 const create=vi.spyOn(api,'syntheticTransaction').mockResolvedValue(transaction);
 render(<Dashboard/>);
 fireEvent.click(await screen.findByRole('button',{name:'Start test upload'}));
 expect(await screen.findByLabelText('Choose evidence file')).toBeInTheDocument();
 expect(screen.getByRole('button',{name:'Upload'})).toBeDisabled();
 expect(screen.getByText('Synthetic test transaction ready. Choose a file below, then click Upload.')).toBeInTheDocument();
 create.mockRestore();
});
