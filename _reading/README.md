## Updates

- 2026-05-25: 🌍 Project Begins!

## Content

- [Keywords Convention](#keywords-convention)
- [Papers](#papers)
    - [Token-wise Strategies](#token-wise-strategies)
        - [Discrete Tokens](#discrete-tokens)
        - [Continuous Tokens](#continuous-tokens)
    - [Internal Mechanisms](#internal-mechanisms)
        - [Structural CoT](#structural-cot)
        - [Representational CoT](#representational-cot)
    - [Analysis and Interpretability](#analysis-and-interpretability)
    - [Applications and Future Directions](#applications-and-future-directions)
- [Resources](#resources)
- [Acknowledgements](#acknowledgements)

## Keywords Convention

![](https://img.shields.io/badge/Coconut-blue) Abbreviation

![](https://img.shields.io/badge/NIPS2024-orange) Conference

![](https://img.shields.io/badge/Reconstruction-lightgray) Main Features

## Papers

### Token-wise Strategies

#### Discrete Tokens

- **Think before you speak: Training language models with pause tokens**  
  *Sachin Goyal,Ziwei Ji, Ankit Singh Rawat, Aditya Krishna Menon, Sanjiv Kumar, Vaishnavh Nagarajan*. [[pdf](https://arxiv.org/pdf/2310.02226)], 2023.10. ![](https://img.shields.io/badge/ICLR2024-orange) ![](https://img.shields.io/badge/pause_tokens-blue) ![](https://img.shields.io/badge/Pretraining-lightgray)
- **Guiding Language Model Reasoning with Planning Tokens**  
  *Xinyi Wang, Lucas Caccia, Oleksiy Ostapenko, Xingdi Yuan, William Yang Wang, Alessandro Sordoni*. [[pdf](https://arxiv.org/pdf/2310.05707)], [[code](https://github.com/WANGXinyiLinda/planning_tokens)], 2023.10. ![](https://img.shields.io/badge/COLM2024-orange) ![](https://img.shields.io/badge/planning_tokens-blue)
- **Thinking Tokens for Language Modeling**  
  *David Herel, Tomas Mikolov*. [[pdf](https://arxiv.org/pdf/2405.08644)],  2024.05. ![](https://img.shields.io/badge/AITP2023-orange) ![](https://img.shields.io/badge/thinking_tokens-blue)
- **Let's think dot by dot: Hidden computation in transformer language models**  
  *Jacob Pfau, William Merrill, Samuel R. Bowman*. [[pdf](https://arxiv.org/pdf/2404.15758)], [[code](https://github.com/JacobPfau/fillerTokens)], 2024.04. ![](https://img.shields.io/badge/COLM2024-orange) ![](https://img.shields.io/badge/filler_tokens-blue)
- **Quiet-STaR: Language Models Can Teach Themselves to Think Before Speaking**  
  *Eric Zelikman, Georges Harik, Yijia Shao, Varuna Jayasiri, Nick Haber, Noah D. Goodman*. [[pdf](https://arxiv.org/pdf/2403.09629)], 2024.03. ![](https://img.shields.io/badge/COLM2024-orange) ![](https://img.shields.io/badge/Quiet--STaR-blue) ![](https://img.shields.io/badge/Pretraining-lightgray)
- **Reasoning to Learn from Latent Thoughts**  
  *Yangjun Ruan, Neil Band, Chris J. Maddison, Tatsunori Hashimoto*. [[pdf](https://arxiv.org/pdf/2503.18866)], [[code](https://github.com/ryoungj/BoLT)], 2025.03. ![](https://img.shields.io/badge/Arxiv-orange) ![](https://img.shields.io/badge/BoLT-blue)
- **Mining Hidden Thoughts from Texts: Evaluating Continual Pretraining with Synthetic Data for LLM Reasoning**  
  *Yoichi Ishibashi, Taro Yano, Masafumi Oyamada*. [[pdf](https://arxiv.org/pdf/2505.10182)], 2025.03. ![](https://img.shields.io/badge/Arxiv-orange) ![](https://img.shields.io/badge/CPT-blue)
- **Disentangling Memory and Reasoning Ability in Large Language Models**  
  *Mingyu Jin, Weidi Luo, Sitao Cheng, Xinyi Wang, Wenyue Hua, Ruixiang Tang, William Yang Wang, Yongfeng Zhang*. [[pdf](https://arxiv.org/pdf/2411.13504)], [[code](https://github.com/MingyuJ666/Disentangling-Memory-and-Reasoning)], 2024.11. ![](https://img.shields.io/badge/Arxiv-orange)
- **Token Assorted: Mixing Latent and Text Tokens for Improved Language Model Reasoning**  
  *DiJia Su, Hanlin Zhu, Yingchen Xu, Jiantao Jiao, Yuandong Tian, Qinqing Zheng*. [[pdf](https://arxiv.org/pdf/2502.03275)], 2025.02.  ![](https://img.shields.io/badge/Arxiv-orange) ![](https://img.shields.io/badge/VQ--VAE-lightgray)
- **Latent Preference Coding: Aligning Large Language Models via Discrete Latent Codes**  
  *Zhuocheng Gong, Jian Guan, Wei Wu, Huishuai Zhang, Dongyan Zhao*. [[pdf](https://arxiv.org/pdf/2505.04993)], 2025.02.  ![](https://img.shields.io/badge/Arxiv-orange) ![](https://img.shields.io/badge/LPC-blue)
- **Efficient Pretraining Length Scaling**  
  *Bohong Wu, Shen Yan, Sijun Zhang, Jianqiao Lu, Yutao Zeng, Ya Wang, Xun Zhou*. [[pdf](https://arxiv.org/pdf/2504.14992)], 2025.04.  ![](https://img.shields.io/badge/Arxiv-orange) ![](https://img.shields.io/badge/PHD--Transformer-blue)
- **Fast Thinking for Large Language Models**  
  *Haoyu Zheng, Zhuonan Wang, Yuqian Yuan, Tianwei Lin, Wenqiao Zhang, Zheqi Lv, Juncheng Li, Siliang Tang, Yueting Zhuang, Hongyang He*. [[pdf](https://arxiv.org/pdf/2509.23633)], 2025.09.  ![](https://img.shields.io/badge/Arxiv-orange)
- **Latent Reasoning with Supervised Thinking States**  
  *Ido Amos, Avi Caciularu, Mor Geva, Amir Globerson, Jonathan Herzig, Lior Shani et al.*. [[pdf](https://arxiv.org/pdf/2602.08332)], 2026.02. ![](https://img.shields.io/badge/Arxiv-orange)  

#### Continuous Tokens 

- **Training Large Language Models to Reason in a Continuous Latent Space**  
  *Shibo Hao, Sainbayar Sukhbaatar, DiJia Su, Xian Li, Zhiting Hu, Jason Weston, Yuandong Tian*. [[pdf](https://arxiv.org/pdf/2412.06769)], [[code](https://github.com/facebookresearch/coconut)], 2024.12. ![](https://img.shields.io/badge/COLM2025-orange) ![](https://img.shields.io/badge/Coconut-blue


## Acknowledgements

If We’ve accidentally missed your papers on the list, please reach out to us, and we’ll make sure to add them as soon as possible!
