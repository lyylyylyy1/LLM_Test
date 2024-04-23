
import openai
import numpy as np
import builtins
import os
from openai import OpenAI
model_text = "gpt-3.5-turbo-instruct"
abandon = 0
flag = True
big_flag = True
# Split word into characters
def split(word):
    return [char for char in word]

secret_file_path = './openai_api_key.txt'
##### set api key
with open(secret_file_path) as f:
    if f:
        os.environ['OPENAI_API_KEY'] = f.read()
    else:
        os.environ['OPENAI_API_KEY'] = getpass("Please enter your openai key:")
openai.api_key = os.environ['OPENAI_API_KEY']
######
# Load all problems
all_prob = np.load('./all_problems.npz', allow_pickle=True)

# GPT-3 settings
openai.api_key = ""
client = OpenAI()
# Loop through all problem types
all_prob_types = builtins.list(all_prob['all_problems'].item().keys())
error_dic=dict.fromkeys(all_prob_types)
for i in all_prob_types:
    error_dic[i] = 0
# Load data if it already exists
all_data_fname = './gpt_3.5_turbo_instruct_matprob_results.npz'
if os.path.exists(all_data_fname):
    data_exists = True
    all_data = np.load('./gpt_3.5_turbo_instruct_matprob_results.npz', allow_pickle=True)
else:
    data_exists = False
# Create data structure for storing results
all_gen_pred = {}
all_gen_correct_pred = {}
all_MC_pred = {}
all_MC_correct_pred = {}
all_alt_MC_correct_pred = {}
for p in range(len(all_prob_types)):
    # Problem type
    prob_type = all_prob_types[p]
    # Load data
    if data_exists:
        all_gen_pred[prob_type] = all_data['all_gen_pred'].item()[prob_type]
        all_gen_correct_pred[prob_type] = all_data['all_gen_correct_pred'].item()[prob_type]
        all_MC_pred[prob_type] = all_data['all_MC_pred'].item()[prob_type]
        all_MC_correct_pred[prob_type] = all_data['all_MC_correct_pred'].item()[prob_type]
        all_alt_MC_correct_pred[prob_type] = all_data['all_alt_MC_correct_pred'].item()[prob_type]
    # Create data structure
    else:
        all_gen_pred[prob_type] = []
        all_gen_correct_pred[prob_type] = []
        all_MC_pred[prob_type] = []
        all_MC_correct_pred[prob_type] = []
        all_alt_MC_correct_pred[prob_type] = []
# Loop over all problem indices
N_prob = 40
for prob_ind in range(N_prob):
    print(str(prob_ind + 1) + ' of ' + str(N_prob) + '...')
    # Loop over all problem types
    for p in range(len(all_prob_types)):
        # Problem type
        prob_type = all_prob_types[p]
        print('Problem type: ' + prob_type + '...')
        perm_invariant = all_prob['all_problems'].item()[prob_type]['perm_invariant']
        prob_type_N_prob = all_prob['all_problems'].item()[prob_type]['prob'].shape[0]
        if prob_ind < prob_type_N_prob and len(all_gen_correct_pred[prob_type]) <= prob_ind:

            # Problem
            prob = all_prob['all_problems'].item()[prob_type]['prob'][prob_ind]
            answer_choices = all_prob['all_problems'].item()[prob_type]['answer_choices'][prob_ind]
            correct_ind = all_prob['all_problems'].item()[prob_type]['correct_ind'][prob_ind]
            correct_answer = answer_choices[correct_ind]

            # Generate prompt 这下面这个prompt就是生成的矩阵问题了
            prompt = ''
            for r in range(3):
                for c in range(3):
                    prompt += '['
                    if not (r == 2 and c == 2):
                        for i in range(len(prob[r][c])):
                            if prob[r][c][i] == -1:
                                prompt += ' '
                            else:
                                prompt += str(prob[r][c][i])
                            if i < len(prob[r][c]) - 1:
                                prompt += ' '
                        prompt += ']'
                        if c < 2:
                            prompt += ' '
                        else:
                            prompt += '\n'

            # Get response
            # response = openai.Completion.create(prompt=prompt, **kwargs)
            response = client.completions.create(
                model=model_text,
                prompt=prompt,
                max_tokens=100,
                temperature=0,
                stop="\n",
                logprobs=1
            )
            response_text = response.choices[0].text
            # Find portion of response corresponding to prediction
            prediction = response_text
            all_gen_pred[prob_type].append(prediction)
            # Get prediction set pred_set是一个数字集合
            pred_set = []
            invalid_char = False
            closing_bracket = False
            for i in range(len(split(prediction))):
                if prediction[i] != ' ':
                    if prediction[i].isdigit():
                        pred_set.append(int(prediction[i]))
                    elif prediction[i] == ']':
                        break
                    else:
                        invalid_char = True
                        break
            
            # Sort answer if problem type is permutation invariant
            if perm_invariant:
                correct_answer = np.sort(correct_answer)
                pred_set = np.sort(pred_set)
            
            # Determine whether prediction is correct
            correct_pred = False
            if not invalid_char and len(pred_set) == len(correct_answer):
                if np.all(pred_set == correct_answer):
                    correct_pred = True
            all_gen_correct_pred[prob_type].append(correct_pred)

            # Get score for generated response

            first_token_ind = np.where(np.array(response.choices[0].logprobs.text_offset) <= len(prompt))[0][-1]
            response_complete = False
            token_ind = first_token_ind
            gen_completion = ''
            while not response_complete:
                token = response.choices[0].logprobs.tokens[token_ind]
                gen_completion += token
                contains_closed_bracket = False
                for i in range(len(token)):
                    if token[i] == ']':
                        contains_closed_bracket = True
                if contains_closed_bracket:
                    response_complete = True
                    if token == ']':
                        last_token_ind = token_ind - 1
                    else:
                        last_token_ind = token_ind
                token_ind += 1
            gen_score = np.mean(response.choices[0].logprobs.token_logprobs[first_token_ind:last_token_ind+1])
            # Evaluate answer choices
            all_choice_logprob = []
            big_flag=True
            for a in range(8):
                # Convert choice to string and remove ','
                choice_str = np.array(split(str(answer_choices[a])))
                choice_str = ''.join(builtins.list(choice_str[choice_str != ',']))
                # Add answer choice to prompt
                prompt_choice = prompt + choice_str[1:]
                # Get average log probability of response
                long_prompt =   "Your output (including symbols) needs to be \"exactly the same\" as the below content:" + prompt_choice
                response = client.completions.create(
                    model=model_text,
                    prompt= long_prompt,
                    max_tokens=100,
                    temperature=0,
                    #stop="\n",
                    logprobs=1
                )
                abandon = 0
                flag = True
                while "\n\n" + prompt_choice != response.choices[0].text and "\n" + prompt_choice != response.choices[0].text:
                    abandon = abandon + 1
                    if abandon >= 5:
                        flag = False
                        big_flag = False
                        break
                    response = client.completions.create(
                        model=model_text,
                        prompt= long_prompt,
                        max_tokens=100,
                        temperature=0,
                        #stop="\n",
                        logprobs=1
                    )
                if flag:
                    first_token_ind = np.where(np.array(response.choices[0].logprobs.text_offset) <= len(long_prompt) + len(prompt))[0][-1]
                    if np.where(np.array(response.choices[0].logprobs.text_offset) == len(long_prompt) + len(response.choices[0].text) - 1)[0].size > 0:
                        last_token_ind = np.where(np.array(response.choices[0].logprobs.text_offset) == len(long_prompt) + len(response.choices[0].text) - 1)[0][0]
                    else:
                        last_token_ind = first_token_ind + 1
                    choice_avg_logprob = np.mean(response.choices[0].logprobs.token_logprobs[first_token_ind:last_token_ind])
                    all_choice_logprob.append(choice_avg_logprob)
                else:
                    all_choice_logprob.append(-99)
            # Select answer
            if big_flag:
                model_choice = np.argmax(all_choice_logprob)
                all_MC_pred[prob_type].append(model_choice)
            # Determine whether multiple choice selection is correct
                MC_correct = model_choice == correct_ind
                all_MC_correct_pred[prob_type].append(MC_correct)
            else:
                error_dic[prob_type] = error_dic[prob_type] + 1
                model_choice = correct_ind
                all_MC_pred[prob_type].append(correct_ind)
                MC_correct = True
                all_MC_correct_pred[prob_type].append(True)

            # Alternative multiple-choice evaluation
            if correct_pred:
                alt_MC_correct = True
            else:
                if MC_correct:
                    all_choice_logprob.append(gen_score)
                    alt_model_choice = np.argmax(all_choice_logprob)
                    alt_MC_correct = alt_model_choice == correct_ind
                else: 
                    alt_MC_correct = False
            all_alt_MC_correct_pred[prob_type].append(alt_MC_correct)

            # Save data
            eval_fname = './gpt_3.5_turbo_instruct_matprob_results.npz'
            np.savez(eval_fname, 
                all_gen_pred=all_gen_pred, all_gen_correct_pred=all_gen_correct_pred, all_MC_pred=all_MC_pred, all_MC_correct_pred=all_MC_correct_pred, all_alt_MC_correct_pred=all_alt_MC_correct_pred, 
                allow_pickle=True)      